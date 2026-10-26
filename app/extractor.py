"""yt-dlp metadata extraction with packaged JavaScript runtime."""
from pathlib import Path
import sys

from .core import ConversionResult, safe_filename, select_format

USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
              'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
REFERER = 'https://www.youtube.com/'


def bundle_root():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))


def find_deno(root=None):
    root = Path(root) if root is not None else bundle_root()
    name = 'deno.exe' if sys.platform == 'win32' else 'deno'
    path = root / 'tools' / name
    if not path.is_file():
        raise RuntimeError('Thiếu Deno đi kèm ứng dụng. Hãy build lại bằng build.bat '
                           'hoặc tải lại bản EXE đầy đủ; không cần cài Deno riêng.')
    return path


class QuietLogger:
    # yt-dlp errors are raised and shown per video. Do not persist signed URLs.
    def debug(self, message): pass
    def warning(self, message): pass
    def error(self, message): pass


def extractor_options(deno):
    return {
        'quiet': True, 'no_warnings': True, 'logger': QuietLogger(),
        'noplaylist': True, 'skip_download': True, 'cachedir': False,
        'socket_timeout': 20, 'retries': 1, 'extractor_retries': 1,
        'js_runtimes': {'deno': {'path': str(deno)}},
        'remote_components': [],
        'http_headers': {'User-Agent': USER_AGENT, 'Referer': REFERER},
    }


def convert_video(url, quality=None, ydl_factory=None):
    if ydl_factory is None:
        from yt_dlp import YoutubeDL
        ydl_factory = YoutubeDL
    deno = find_deno()
    with ydl_factory(extractor_options(deno)) as ydl:
        info = ydl.extract_info(url, download=False, process=False)
    if not info or info.get('_type', 'video') not in ('video',):
        raise ValueError('Chỉ hỗ trợ từng video YouTube; không mở rộng playlist.')
    f = select_format(info, quality)
    title = info.get('title') or info.get('id') or 'video'
    headers = {'user-agent': USER_AGENT, 'referer': REFERER}
    for source in (info.get('http_headers') or {}, f.get('http_headers') or {}):
        for key, value in source.items():
            if key.lower() in headers:
                headers[key.lower()] = value
    return ConversionResult(url, title, safe_filename(title, f.get('ext')), f['url'],
                            f.get('height'), requested_quality=quality,
                            headers={'User-Agent': headers['user-agent'], 'Referer': headers['referer']})
