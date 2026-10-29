"""Exact-quality media download and local MP4 assembly, separate from IDM URLs."""
from pathlib import Path
import os
import re
import shutil
import sys
import subprocess
import tempfile
import time
from urllib.parse import urlsplit

from .core import ConversionResult, _requires_auth, safe_filename, unique_filename, video_quality
from .extractor import bundle_root, extractor_options, find_deno


def find_ffmpeg():
    import imageio_ffmpeg
    path = Path(imageio_ffmpeg.get_ffmpeg_exe()).resolve()
    if not path.is_file():
        raise RuntimeError('Thiếu FFmpeg đi kèm ứng dụng. Hãy build lại hoặc tải bản EXE đầy đủ.')
    if getattr(sys, 'frozen', False) and not path.is_relative_to(bundle_root().resolve()):
        raise RuntimeError('Bản EXE thiếu FFmpeg được đóng gói; không dùng FFmpeg ngoài ứng dụng.')
    return str(path)


def _usable(f):
    try:
        url = f.get('url') or ''
        parsed = urlsplit(url)
    except ValueError:
        return False
    return (parsed.scheme in ('http', 'https') and bool(parsed.hostname)
            and not parsed.username and not parsed.password and '\n' not in url and '\r' not in url
            and not f.get('has_drm') and not _requires_auth(f.get('http_headers'))
            and f.get('protocol') in (None, 'http', 'https', 'm3u8', 'm3u8_native', 'http_dash_segments', 'dash'))


def select_download_formats(info, quality=None):
    if quality is not None and quality not in (360, 480, 720, 1080):
        raise ValueError('Mức chất lượng không hợp lệ.')
    if info.get('is_live') or info.get('live_status') == 'is_live':
        raise ValueError('Không tải livestream đang phát; hãy thử sau khi phát xong.')
    if _requires_auth(info.get('http_headers')):
        raise ValueError('Video yêu cầu đăng nhập/cookie; chưa hỗ trợ trong ứng dụng.')
    formats = [f for f in info.get('formats') or [] if _usable(f)]
    audio = [f for f in formats if f.get('vcodec') == 'none' and f.get('acodec') not in (None, '', 'none')]
    best_audio = max(audio, key=lambda f: (f.get('language_preference') or 0,
        str(f.get('acodec')).startswith(('mp4a', 'aac')), f.get('abr') or f.get('tbr') or 0), default=None)
    videos = [f for f in formats if f.get('vcodec') not in (None, '', 'none')
              and f.get('acodec') not in (None, '')
              and (quality is None or video_quality(f.get('width'), f.get('height')) == quality)]
    videos.sort(key=lambda f: (video_quality(f.get('width'), f.get('height')) or 0,
        str(f.get('vcodec')).startswith(('avc1', 'h264')), f.get('ext') == 'mp4',
        f.get('tbr') or 0, f.get('fps') or 0), reverse=True)
    for video in videos:
        if video.get('acodec') != 'none':
            return video, None
        if best_audio is not None:
            return video, best_audio
    wanted = f'đúng {quality}p' if quality is not None else 'phù hợp'
    raise ValueError(f'Không có video {wanted} kèm âm thanh có thể tải. Không tải chất lượng khác hoặc nâng độ phân giải.')


def _flags():
    return {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}


def merge_media(video, audio, output, ffmpeg, audio_codec, progress):
    command = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y', '-i', str(video)]
    if audio is not None:
        command += ['-i', str(audio)]
    command += ['-map', '0:v:0', '-map', '1:a:0' if audio is not None else '0:a:0',
                '-c:v', 'copy', '-c:a', 'copy' if str(audio_codec).startswith(('mp4a', 'aac')) else 'aac',
                '-movflags', '+faststart', str(output)]
    progress('Ghép hình và tiếng thành MP4 (giữ nguyên độ phân giải)...')
    started = time.monotonic()
    with subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, **_flags()) as process:
        while True:
            try:
                _, stderr = process.communicate(timeout=1)
                break
            except subprocess.TimeoutExpired:
                elapsed = time.monotonic() - started
                progress(f'Ghép MP4 đang chạy {elapsed:.0f}s...')
                if elapsed >= 1800:
                    process.kill()
                    process.communicate()
                    raise RuntimeError('Ghép MP4 vượt quá 30 phút; đã dừng FFmpeg.')
        if process.returncode != 0:
            raise RuntimeError(f'Không ghép được MP4 (FFmpeg exit {process.returncode}): ' + stderr.decode('utf-8', errors='replace')[-2000:])


def inspect_media(path, ffmpeg):
    # Maps require both AV streams; decode a small sample and inspect input dimensions.
    result = subprocess.run([ffmpeg, '-hide_banner', '-nostdin', '-i', str(path),
        '-map', '0:v:0', '-map', '0:a:0', '-t', '0.05', '-f', 'null', '-'],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=60, **_flags())
    text = result.stderr.decode('utf-8', errors='replace')
    dimensions = re.search(r'Stream #0:\d+[^\n]*Video:[^\n]*?\b(\d{2,5})x(\d{2,5})\b', text)
    if result.returncode != 0 or dimensions is None:
        raise RuntimeError('File MP4 không có đủ hình/tiếng hoặc không đọc được độ phân giải: ' + text[-1000:])
    return int(dimensions[1]), int(dimensions[2])


def _publish_no_overwrite(source, folder, filename):
    used = {p.name.casefold() for p in folder.iterdir()}
    while True:
        name = unique_filename(filename, used)
        target = folder / name
        try:
            handle = target.open('xb')
        except FileExistsError:
            continue
        try:
            with handle, source.open('rb') as incoming:
                shutil.copyfileobj(incoming, handle)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return target


def download_video(url, quality, folder, *, progress=None, ydl_factory=None):
    if ydl_factory is None:
        from yt_dlp import YoutubeDL
        ydl_factory = YoutubeDL
    emit = progress or (lambda message: None)
    folder = Path(folder).resolve()
    if not folder.is_dir():
        raise ValueError('Hãy chọn một thư mục tải hợp lệ.')
    deno, ffmpeg = find_deno(), find_ffmpeg()
    options = extractor_options(deno)
    options['ffmpeg_location'] = ffmpeg
    emit('Đang đọc các định dạng video và âm thanh...')
    with ydl_factory(options) as ydl:
        info = ydl.extract_info(url, download=False, process=False)
    if not info or info.get('_type', 'video') != 'video':
        raise ValueError('Chỉ hỗ trợ video đơn lẻ, không tự mở rộng playlist.')
    video, audio = select_download_formats(info, quality)
    title = info.get('title') or info.get('id') or 'video'
    with tempfile.TemporaryDirectory(prefix='.yt-converter-', dir=folder) as temporary:
        work = Path(temporary)
        sources = []
        for index, selected in enumerate([video] + ([audio] if audio is not None else [])):
            label = 'Tải hình' if index == 0 else 'Tải tiếng'
            emit(label + '...')
            last = [0.0]
            def hook(data, label=label, last=last):
                now = time.monotonic()
                if data.get('status') != 'finished' and now - last[0] < .25:
                    return
                last[0] = now
                size = data.get('downloaded_bytes') or 0
                total = data.get('total_bytes') or data.get('total_bytes_estimate')
                prefix = '~' if not data.get('total_bytes') and total else ''
                detail = f'{prefix}{min(100, size / total * 100):.1f}% | ' if total else ''
                emit(f'{label}: {detail}{size / 1048576:.2f} MiB')
            params = dict(options, skip_download=False, noprogress=True, fixup='never',
                          skip_unavailable_fragments=False, fragment_retries=1,
                          outtmpl=str(work / f'stream{index}.%(ext)s'), progress_hooks=[hook],
                          format=lambda context: iter([context['formats'][0]]))
            with ydl_factory(params) as ydl:
                processed = ydl.process_ie_result({**info, 'formats': [dict(selected)]}, download=True)
                downloaded = Path(ydl.prepare_filename(processed))
            if not downloaded.is_file() or downloaded.stat().st_size == 0:
                raise RuntimeError('Tải không hoàn tất; chưa có file dữ liệu hợp lệ.')
            sources.append(downloaded)
        merged = work / 'merged.mp4'
        merge_media(sources[0], sources[1] if len(sources) > 1 else None,
                    merged, ffmpeg, (audio or video).get('acodec'), emit)
        emit('Kiểm tra hình, tiếng và độ phân giải MP4...')
        width, height = inspect_media(merged, ffmpeg)
        if quality is not None and video_quality(width, height) != quality:
            raise ValueError(f'File tải về không đạt đúng {quality}p; không lưu kết quả sai chất lượng.')
        emit('Đang lưu MP4 đã kiểm tra...')
        saved = _publish_no_overwrite(merged, folder, safe_filename(title, 'mp4'))
    emit(f'Đã lưu: {saved}')
    return ConversionResult(url, title, saved.name, height=height, width=width,
                            requested_quality=quality, local_path=str(saved))
