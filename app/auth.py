"""Explicit local cookie sources; credentials stay in an in-memory yt-dlp jar."""
from contextlib import contextmanager
from dataclasses import dataclass
from http.cookiejar import Cookie
from pathlib import Path
import time

BROWSER_HELP = ('Không đọc được cookie trình duyệt. Hãy đóng hoàn toàn trình duyệt rồi thử lại; '
                'kiểm tra đúng hồ sơ. Chrome/Edge trên Windows có thể chặn giải mã cookie. '
                'Hãy dùng Firefox đã mở video được, hoặc xuất cookie YouTube thành file '
                'Netscape cookies.txt rồi chọn file trong mục Xác thực YouTube.')
BOT_HELP = ('Xác thực YouTube: YouTube yêu cầu xác nhận không phải bot. Mở video trên trình duyệt '
            'cùng máy/mạng, hoàn tất xác minh hoặc đăng nhập nếu được yêu cầu. Trong mục '
            'Xác thực YouTube, chọn trình duyệt đó hoặc file cookies.txt mới xuất, rồi chạy lại. '
            'Nếu đã dùng cookie, hãy làm mới phiên và thử lại sau; cookie không bảo đảm gỡ được chặn IP.')
FILE_HELP = ('Không đọc được cookie YouTube hợp lệ. Chọn file cookies.txt định dạng Netscape '
             '(không phải JSON/danh sách link), có cookie YouTube chưa hết hạn; xuất lại nếu cần.')


@dataclass(frozen=True)
class CookieSource:
    browser: str | None = None
    file: str | Path | None = None
    profile: str | None = None

    def __post_init__(self):
        if bool(self.browser) == bool(self.file):
            raise ValueError('Chọn một nguồn cookie: trình duyệt hoặc file cookies.txt.')
        if self.browser and self.browser not in ('firefox', 'chrome', 'edge'):
            raise ValueError('Trình duyệt cookie không được hỗ trợ.')
        if self.profile and not self.browser:
            raise ValueError('Hồ sơ chỉ dùng với nguồn cookie trình duyệt.')


def _allowed_domain(domain):
    domain = domain.lstrip('.').lower()
    return any(domain == host or domain.endswith('.' + host)
               for host in ('youtube.com', 'googlevideo.com', 'youtu.be'))


def _file_cookies(path):
    from yt_dlp.cookies import YoutubeDLCookieJar
    jar = YoutubeDLCookieJar()
    # Parse strictly instead of yt-dlp's permissive loader, which can print a
    # rejected line (including its secret value). Never pass cookiefile to YDL:
    # YDL.close() would otherwise rewrite the user's original file.
    try:
        path = Path(path)
        if not path.is_file() or path.stat().st_size > 10 * 1024 * 1024:
            raise ValueError
        lines = path.read_text(encoding='utf-8-sig').splitlines()
        if not lines or lines[0].strip() not in ('# Netscape HTTP Cookie File', '# HTTP Cookie File'):
            raise ValueError
        for line in lines[1:]:
            rest = {}
            if line.startswith('#HttpOnly_'):
                line = line[len('#HttpOnly_'):]
                rest['HTTPOnly'] = ''
            elif line.startswith('#') or not line.strip():
                continue
            domain, subdomains, path_value, secure, expires, name, value = line.split('\t')
            if (subdomains not in ('TRUE', 'FALSE') or secure not in ('TRUE', 'FALSE')
                    or domain.startswith('.') != (subdomains == 'TRUE')
                    or not path_value.startswith('/') or not name
                    or (expires and not expires.isascii()) or (expires and not expires.isdecimal())):
                raise ValueError
            expiration = int(expires) if expires and int(expires) else None
            if not _allowed_domain(domain) or expiration is not None and expiration <= time.time():
                continue
            jar.set_cookie(Cookie(0, name, value, None, False, domain, subdomains == 'TRUE',
                domain.startswith('.'), path_value, True, secure == 'TRUE', expiration,
                expiration is None, None, None, rest))
    except (OSError, ValueError, UnicodeError, OverflowError):
        raise ValueError(FILE_HELP) from None
    if not any(cookie.domain.lstrip('.').lower().endswith('youtube.com') for cookie in jar):
        raise ValueError(FILE_HELP)
    return jar


class _CookieLogger:
    """Track partial browser-read failures without printing cookie diagnostics."""
    def __init__(self):
        self.failed = False

    def debug(self, message, **kwargs): pass
    def info(self, message, **kwargs): pass

    def warning(self, message, **kwargs):
        self.failed = True

    error = warning

    def progress_bar(self):
        return None


def _load_cookies(auth):
    if auth.file:
        return _file_cookies(auth.file)
    from yt_dlp.cookies import extract_cookies_from_browser, YoutubeDLCookieJar
    try:
        logger = _CookieLogger()
        loaded = extract_cookies_from_browser(auth.browser, auth.profile, logger)
        # yt-dlp can return a partial jar when Chromium cookie decryption fails.
        # A surviving preference cookie does not establish a usable session.
        if logger.failed:
            raise ValueError('Incomplete browser cookie read')
        jar = YoutubeDLCookieJar()
        for cookie in loaded:
            if _allowed_domain(cookie.domain) and not cookie.is_expired():
                jar.set_cookie(cookie)
        if not any(cookie.domain.lstrip('.').lower().endswith('youtube.com') for cookie in jar):
            raise ValueError('No YouTube cookies')
        return jar
    except Exception:
        raise ValueError(BROWSER_HELP) from None


@contextmanager
def youtube_session(options, factory, *, auth=None, cookiejar=None):
    try:
        with factory(options) as ydl:
            if cookiejar is not None:
                ydl.cookiejar = cookiejar
            elif auth is not None:
                ydl.cookiejar = _load_cookies(auth)
            yield ydl
    except Exception as exc:
        text = str(exc).lower()
        if 'sign in to confirm' in text and ('bot' in text or 'age' in text):
            raise ValueError(BOT_HELP) from None
        raise
