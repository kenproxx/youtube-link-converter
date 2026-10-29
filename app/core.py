"""Pure conversion rules; no GUI, network or process side effects."""
from dataclasses import dataclass, field, replace
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

QUALITY_OPTIONS = {'Tốt nhất có thể': None, '360p': 360, '480p': 480, '720p': 720, '1080p': 1080}
VIDEO_ID = re.compile(r'^[A-Za-z0-9_-]{11}$')
HOSTS = {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com',
         'youtu.be', 'www.youtu.be'}
RESERVED = re.compile(r'^(CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9¹²³]|LPT[1-9¹²³]) *?(?:\.|$)', re.I)


@dataclass(frozen=True)
class ConversionResult:
    source: str
    title: str = ''
    filename: str = ''
    url: str = ''
    height: int | None = None
    error: str | None = None
    requested_quality: int | None = None
    headers: dict = field(default_factory=dict)
    width: int | None = None
    local_path: str = ''

    @property
    def quality(self):
        return video_quality(self.width, self.height)


def parse_urls(text):
    """Return canonical unique video URLs and line-specific validation errors."""
    urls, errors, seen = [], [], set()
    for line_no, line in enumerate(text.lstrip('\ufeff').splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            p = urlsplit(line)
            if (p.scheme not in ('http', 'https') or p.hostname not in HOSTS
                    or p.username or p.password or p.port is not None):
                raise ValueError
            parts = p.path.strip('/').split('/')
            if p.hostname in ('youtu.be', 'www.youtu.be') and len(parts) == 1:
                vid = parts[0]
            elif p.path == '/watch':
                vid = parse_qs(p.query).get('v', [''])[0]
            elif len(parts) == 2 and parts[0] in ('shorts', 'live', 'embed'):
                vid = parts[1]
            else:
                raise ValueError
            if not VIDEO_ID.fullmatch(vid):
                raise ValueError
            if vid not in seen:
                urls.append(f'https://www.youtube.com/watch?v={vid}')
                seen.add(vid)
        except ValueError:
            errors.append(f'Dòng {line_no}: cần link video YouTube hợp lệ (không nhận playlist).')
    return urls, errors


def _requires_auth(headers):
    return any(k.lower() in ('cookie', 'authorization') and v for k, v in (headers or {}).items())


def _unsupported_headers(headers):
    standard = {'user-agent', 'referer', 'accept', 'accept-language', 'accept-encoding',
                'connection', 'dnt', 'upgrade-insecure-requests'}
    return any(k.lower() not in standard and v for k, v in (headers or {}).items())


def video_quality(width, height):
    """Use yt-dlp's resolution convention: the smaller known video dimension."""
    if not height or height <= 0:
        return None
    return min(width, height) if width and width > 0 else height


def select_format(info, quality=None):
    if quality is not None and quality not in (360, 480, 720, 1080):
        raise ValueError('Mức chất lượng không hợp lệ.')
    if info.get('is_live') or info.get('live_status') == 'is_live':
        raise ValueError('Video đang phát trực tiếp; hãy thử lại sau khi phát xong.')
    if info.get('cookies') or _requires_auth(info.get('http_headers')) or _unsupported_headers(info.get('http_headers')):
        raise ValueError('Link cần xác thực hoặc header riêng không thể chuyển trực tiếp sang IDM. Hãy dùng Tải MP4 đủ tiếng.')
    candidates = []
    combined_levels, separate_levels = set(), set()
    for f in info.get('formats') or []:
        url = f.get('url') or ''
        try:
            p = urlsplit(url)
        except ValueError:
            continue
        if (p.scheme not in ('http', 'https') or not p.hostname
                or p.username or p.password or '\n' in url or '\r' in url
                or (f.get('protocol') or p.scheme) not in ('http', 'https')
                or f.get('vcodec') in (None, '', 'none')
                or f.get('acodec') in (None, '')
                or f.get('has_drm') or f.get('manifest_url') or f.get('fragments')
                or p.path.lower().endswith(('.m3u8', '.mpd'))
                or f.get('cookies') or _requires_auth(f.get('http_headers')) or _unsupported_headers(f.get('http_headers'))):
            continue
        level = video_quality(f.get('width'), f.get('height'))
        if f.get('acodec') == 'none':
            if level:
                separate_levels.add(level)
            continue
        if level:
            combined_levels.add(level)
        if quality is not None and level != quality:
            continue
        candidates.append(f)
    if not candidates:
        wanted = f'đúng {quality}p' if quality is not None else 'phù hợp'
        available = ', '.join(f'{q}p' for q in sorted(combined_levels)) or 'không có'
        message = f'Không có link một file chứa cả hình và tiếng {wanted}. Không lấy link chất lượng khác. '
        message += f'Chất lượng một file yt-dlp tìm thấy: {available}.'
        if any(f.get('cookies') or _requires_auth(f.get('http_headers')) for f in info.get('formats') or []):
            message += ' Có định dạng cần cookie/xác thực; hãy dùng Tải MP4 đủ tiếng để tải bằng phiên đã chọn.'
        if quality in separate_levels or (quality is None and separate_levels):
            levels = [quality] if quality is not None else sorted(separate_levels)
            message += (' Có luồng hình riêng ' + ', '.join(f'{q}p' for q in levels)
                        + '; cần tải và ghép thêm âm thanh bằng FFmpeg để có file đầy đủ tiếng.')
        raise ValueError(message)
    return max(candidates, key=lambda f: (video_quality(f.get('width'), f.get('height')) or 0, f.get('ext') == 'mp4',
                                        f.get('tbr') or 0, str(f.get('format_id', ''))))


def _truncate_utf16(text, limit):
    return text.encode('utf-16-le')[:limit * 2].decode('utf-16-le', errors='ignore')


def safe_filename(title, ext):
    ext = ext if re.fullmatch(r'[A-Za-z0-9]{1,8}', ext or '') else 'mp4'
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', title or '').strip().rstrip('. ')
    stem = stem or 'video'
    if RESERVED.match(stem):
        stem = '_' + stem
    stem = _truncate_utf16(stem, 180 - len(ext) - 1).rstrip('. ')
    return f'{stem}.{ext}'


def unique_filename(filename, used):
    stem, ext = filename.rsplit('.', 1)
    candidate, i = filename, 2
    while candidate.casefold() in used:
        suffix = f' ({i})'
        short = _truncate_utf16(stem, 180 - len(ext) - 1 - len(suffix)).rstrip('. ')
        candidate = f'{short}{suffix}.{ext}'
        i += 1
    used.add(candidate.casefold())
    return candidate


def run_batch(urls, quality, cancel, convert):
    used = set()
    for url in urls:
        if cancel.is_set():
            break
        try:
            r = convert(url, quality)
            if not r.error:
                if quality is not None and r.quality != quality:
                    actual = f'{r.quality}p' if r.quality else 'không xác định'
                    raise ValueError(f'Yêu cầu đúng {quality}p nhưng nhận {actual}; không lấy link này.')
                r = replace(r, filename=unique_filename(r.filename, used), requested_quality=quality)
        except Exception as exc:
            r = ConversionResult(url, error=str(exc), requested_quality=quality)
        yield r


def export_txt(path, results):
    urls = [r.url for r in results if not r.error and r.url]
    with Path(path).open('w', encoding='utf-8', newline='\n') as f:
        f.write(''.join(url + '\n' for url in urls))
