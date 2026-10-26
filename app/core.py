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


def select_format(info, quality=None):
    if quality is not None and quality not in (360, 480, 720, 1080):
        raise ValueError('Mức chất lượng không hợp lệ.')
    if info.get('is_live') or info.get('live_status') == 'is_live':
        raise ValueError('Video đang phát trực tiếp; hãy thử lại sau khi phát xong.')
    if _requires_auth(info.get('http_headers')) or _unsupported_headers(info.get('http_headers')):
        raise ValueError('Link cần xác thực hoặc header riêng không thể chuyển trực tiếp sang IDM.')
    candidates = []
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
                or f.get('acodec') in (None, '', 'none')
                or f.get('has_drm') or f.get('manifest_url') or f.get('fragments')
                or p.path.lower().endswith(('.m3u8', '.mpd'))
                or _requires_auth(f.get('http_headers')) or _unsupported_headers(f.get('http_headers'))):
            continue
        height = f.get('height')
        if quality is not None and (not height or height > quality):
            continue
        candidates.append(f)
    if not candidates:
        raise ValueError('Không có link tải trực tiếp chứa cả hình và tiếng ở mức đã chọn. '
                         'Thử Tốt nhất có thể; ứng dụng không ghép hai luồng riêng.')
    return max(candidates, key=lambda f: (f.get('height') or 0, f.get('ext') == 'mp4',
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
                r = replace(r, filename=unique_filename(r.filename, used), requested_quality=quality)
        except Exception as exc:
            r = ConversionResult(url, error=str(exc), requested_quality=quality)
        yield r


def export_txt(path, results):
    urls = [r.url for r in results if not r.error and r.url]
    with Path(path).open('w', encoding='utf-8', newline='\n') as f:
        f.write(''.join(url + '\n' for url in urls))
