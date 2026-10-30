import contextlib
import io
from pathlib import Path
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from app.extractor import convert_video, extractor_options


class CookieAuthTests(unittest.TestCase):
    def source(self, **kwargs):
        from app.auth import CookieSource
        return CookieSource(**kwargs)

    def test_cookie_file_authenticates_real_requests_without_rewriting_file(self):
        # Dropping the jar from a later yt-dlp instance must break this request.
        from app.auth import youtube_session
        from yt_dlp import YoutubeDL
        from yt_dlp.networking import Request
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                good = self.headers.get('Cookie') == 'SESSION=fixture-secret'
                self.send_response(200 if good else 401)
                self.end_headers()
                self.wfile.write(b'authenticated' if good else b'no session')
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'cookies.txt'
                original = '# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tFALSE\t0\tSESSION\tfixture-secret\n'
                path.write_text(original, encoding='utf-8')
                options = extractor_options(Path('/unused'))
                options['proxy'] = ''  # localhost only, never an external request
                with youtube_session(options, YoutubeDL, auth=self.source(file=path)) as first:
                    # Keep domain checking real; only redirect the hostname to localhost.
                    for cookie in first.cookiejar:
                        cookie.domain, cookie.domain_specified, cookie.domain_initial_dot = '127.0.0.1', False, False
                    jar = first.cookiejar
                with youtube_session(options, YoutubeDL, cookiejar=jar) as second:
                    with second.urlopen(Request(f'http://127.0.0.1:{server.server_port}/')) as response:
                        self.assertEqual(response.read(), b'authenticated')
                self.assertEqual(path.read_text(encoding='utf-8'), original)
                self.assertEqual(list(Path(tmp).iterdir()), [path])
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_invalid_expired_and_unrelated_files_are_rejected_without_cookie_leaks(self):
        from app.auth import youtube_session
        from yt_dlp import YoutubeDL
        samples = [
            '[{"value":"private-secret"}]',
            '# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tFALSE\t0\tSESSION\tprivate-secret\textra\n',
            '# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tFALSE\t1\tSESSION\tprivate-secret\n',
            '# Netscape HTTP Cookie File\n.evil-youtube.com\tTRUE\t/\tFALSE\t0\tSESSION\tprivate-secret\n',
            '# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tFALSE\tnan\tSESSION\tprivate-secret\n',
        ]
        for sample in samples:
            with self.subTest(sample=samples.index(sample)), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'cookies.txt'
                path.write_text(sample, encoding='utf-8')
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    with self.assertRaises(ValueError) as caught:
                        with youtube_session(extractor_options(Path('/unused')), YoutubeDL, auth=self.source(file=path)):
                            self.fail('Invalid cookies must fail before any request')
                self.assertIn('cookie', str(caught.exception).lower())
                self.assertNotIn('private-secret', str(caught.exception) + out.getvalue() + err.getvalue())
                self.assertEqual(path.read_text(encoding='utf-8'), sample)

    def test_browser_load_is_explicit_filters_domains_and_preserves_profile(self):
        from app.auth import youtube_session
        from yt_dlp import YoutubeDL
        from yt_dlp.cookies import YoutubeDLCookieJar
        from http.cookiejar import Cookie
        jar = YoutubeDLCookieJar()
        for domain in ('.youtube.com', '.unrelated.example'):
            jar.set_cookie(Cookie(0, 'SESSION', 'fixture', None, False, domain, True, True,
                '/', True, True, int(time.time()) + 3600, False, None, None, {}))
        with patch('yt_dlp.cookies.extract_cookies_from_browser', return_value=jar) as browser:
            with youtube_session(extractor_options(Path('/unused')), YoutubeDL):
                pass
            self.assertEqual(browser.call_count, 0)
            with youtube_session(extractor_options(Path('/unused')), YoutubeDL,
                                 auth=self.source(browser='firefox', profile='Work')) as ydl:
                self.assertEqual([cookie.domain for cookie in ydl.cookiejar], ['.youtube.com'])
            self.assertEqual(browser.call_args.args[:2], ('firefox', 'Work'))

    def test_browser_lock_or_decryption_failure_explains_fallback(self):
        from app.auth import youtube_session
        from yt_dlp import YoutubeDL
        for message in ('Could not copy Chrome cookie database', 'Failed to decrypt with DPAPI'):
            with self.subTest(message=message), patch('yt_dlp.cookies.extract_cookies_from_browser', side_effect=RuntimeError(message)):
                with self.assertRaisesRegex(ValueError, 'Firefox.*cookies.txt'):
                    with youtube_session(extractor_options(Path('/unused')), YoutubeDL,
                                         auth=self.source(browser='chrome')):
                        self.fail('A failed browser session cannot proceed anonymously')

    def test_real_firefox_sqlite_profile_loads_without_modifying_database(self):
        import sqlite3
        from app.auth import youtube_session
        from yt_dlp import YoutubeDL
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / 'cookies.sqlite'
            with contextlib.closing(sqlite3.connect(database)) as connection, connection:
                connection.execute('pragma user_version=16')
                connection.execute('create table moz_cookies (host text, name text, value text, path text, expiry integer, isSecure integer, originAttributes text)')
                connection.execute('insert into moz_cookies values (?, ?, ?, ?, ?, ?, ?)',
                    ('.youtube.com', 'SESSION', 'fixture-secret', '/', (int(time.time()) + 3600) * 1000, 1, ''))
            # Windows cannot delete this fixture while its writer is still open.
            # Check the handle lifetime on every OS; close it even if this fails.
            try:
                with self.assertRaises(sqlite3.ProgrammingError):
                    connection.execute('select 1')
            finally:
                connection.close()
            original = database.read_bytes()
            with youtube_session(extractor_options(Path('/unused')), YoutubeDL,
                                 auth=self.source(browser='firefox', profile=tmp)) as ydl:
                self.assertEqual(ydl.cookiejar.get_cookie_header('https://www.youtube.com/'), 'SESSION=fixture-secret')
            self.assertEqual(database.read_bytes(), original)

    def test_partially_decrypted_chromium_jar_is_not_silently_accepted(self):
        import sqlite3
        from app.auth import youtube_session
        from yt_dlp import YoutubeDL
        from yt_dlp.cookies import WindowsChromeCookieDecryptor
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.closing(sqlite3.connect(Path(tmp) / 'Cookies')) as connection, connection:
                connection.execute('create table meta (key text, value text)')
                connection.execute("insert into meta values ('version', '24')")
                connection.execute('create table cookies (host_key text, name text, value text, encrypted_value blob, path text, expires_utc integer, is_secure integer)')
                connection.executemany('insert into cookies values (?, ?, ?, ?, ?, ?, ?)', [
                    ('.youtube.com', 'PREF', 'fixture-pref', b'', '/', 0, 1),
                    ('.youtube.com', 'SID', '', b'v10fixture-encrypted-cookie', '/', 0, 1)])
            try:
                with self.assertRaises(sqlite3.ProgrammingError):
                    connection.execute('select 1')
            finally:
                connection.close()
            def decryptor(root, browser, logger, **kwargs):
                return WindowsChromeCookieDecryptor(root, logger, meta_version=24)
            with patch('yt_dlp.cookies.get_cookie_decryptor', side_effect=decryptor), \
                 patch('yt_dlp.cookies._get_windows_v10_key', return_value=None):
                with self.assertRaisesRegex(ValueError, 'Firefox.*cookies.txt'):
                    with youtube_session(extractor_options(Path('/unused')), YoutubeDL,
                                         auth=self.source(browser='chrome', profile=tmp)):
                        pass

    def test_authenticated_extraction_keeps_cookies_out_of_idm_result(self):
        from yt_dlp import YoutubeDL
        class MetadataYDL(YoutubeDL):
            def extract_info(self, *args, **kwargs):
                authenticated = self.cookiejar.get_cookie_header('https://www.youtube.com/')
                if authenticated != 'SESSION=fixture-secret':
                    raise AssertionError('Selected cookie source did not reach extraction')
                return {'id': 'abcdefghijk', 'title': 'Title', 'formats': [dict(format_id='18',
                    ext='mp4', height=360, acodec='mp4a', vcodec='avc1', protocol='https',
                    url='https://media.example/video')]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'cookies.txt'
            path.write_text('# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tFALSE\t0\tSESSION\tfixture-secret\n')
            with patch('app.extractor.find_deno', return_value=Path('/unused')):
                result = convert_video('https://youtube.com/watch?v=abcdefghijk', 360, MetadataYDL,
                                       auth=self.source(file=path))
            self.assertEqual(result.url, 'https://media.example/video')
            self.assertNotIn('fixture-secret', repr(result))
