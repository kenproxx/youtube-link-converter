import tempfile
import unittest
from pathlib import Path, PurePosixPath, PureWindowsPath
from unittest.mock import patch
from threading import Event

from app.extractor import convert_video, extractor_options, find_deno
from app.core import run_batch


class ExtractorTests(unittest.TestCase):
    def test_bot_verification_error_has_actionable_vietnamese_recovery(self):
        from yt_dlp.utils import DownloadError
        class BlockedYDL:
            def __init__(self, opts): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def extract_info(self, *args, **kwargs):
                raise DownloadError("ERROR: [youtube] pvalSxVT9to: Sign in to confirm you're not a bot. Use --cookies-from-browser or --cookies")
        with patch('app.extractor.find_deno', return_value=Path('/tools/deno')):
            result = list(run_batch(['https://youtube.com/watch?v=pvalSxVT9to'], 1080, Event(),
                lambda url, quality: convert_video(url, quality, BlockedYDL)))[0]
        self.assertRegex(result.error, 'Xác thực YouTube.*cookie')
        self.assertFalse(result.url)

    def test_options_disable_remote_code_and_use_explicit_runtime(self):
        # Check both path flavours on every host, including Windows paths with spaces.
        cases = [
            (PurePosixPath('/bundle/tools/deno.exe'), '/bundle/tools/deno.exe'),
            (PureWindowsPath('C:/Build folder/tools/deno.exe'), r'C:\Build folder\tools\deno.exe'),
        ]
        for deno, expected_path in cases:
            with self.subTest(path=expected_path):
                opts = extractor_options(deno)
                self.assertEqual(opts['js_runtimes'], {'deno': {'path': expected_path}})
                self.assertEqual(opts['remote_components'], [])
                self.assertTrue(opts['noplaylist'])
                self.assertLessEqual(opts['socket_timeout'], 20)
                self.assertEqual(opts['retries'], 1)

    def test_missing_runtime_reports_actionable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, 'Deno'):
                find_deno(Path(tmp))

    def test_extracts_without_media_download_and_uses_video_title(self):
        info = {'title': 'Bài hát', 'formats': [dict(format_id='18', ext='mp4', height=360,
            acodec='mp4a', vcodec='avc1', protocol='https', url='https://media.example/video')]}
        class FakeYDL:
            def __init__(self, opts):
                self.opts = opts
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def extract_info(self, url, download=True, process=True):
                if download or process:
                    raise AssertionError('Must request metadata only')
                return info
        with patch('app.extractor.find_deno', return_value=Path('/tools/deno')):
            result = convert_video('https://www.youtube.com/watch?v=abcdefghijk', 360, FakeYDL)
        self.assertEqual(result.title, 'Bài hát')
        self.assertEqual(result.filename, 'Bài hát.mp4')
        self.assertEqual(result.height, 360)
        self.assertEqual(result.url, 'https://media.example/video')
        self.assertEqual(result.headers['Referer'], 'https://www.youtube.com/')
        self.assertIn('Mozilla/5.0', result.headers['User-Agent'])

    def test_playlist_response_is_rejected(self):
        class FakeYDL:
            def __init__(self, opts): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def extract_info(self, *a, **kw): return {'_type': 'playlist', 'entries': []}
        with patch('app.extractor.find_deno', return_value=Path('/tools/deno')):
            with self.assertRaises(ValueError):
                convert_video('https://youtube.com/watch?v=abcdefghijk', None, FakeYDL)

    def test_portrait_1080_keeps_real_dimensions_and_normalized_quality(self):
        class FakeYDL:
            def __init__(self, opts): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def extract_info(self, *a, **kw):
                return {'title': 'Portrait', 'formats': [dict(format_id='portrait', ext='mp4',
                    width=1080, height=1920, acodec='mp4a', vcodec='avc1',
                    protocol='https', url='https://media.example/portrait')]}
        with patch('app.extractor.find_deno', return_value=Path('/tools/deno')):
            result = convert_video('https://youtube.com/watch?v=abcdefghijk', 1080, FakeYDL)
        self.assertEqual(result.quality, 1080)
        self.assertEqual((result.width, result.height), (1080, 1920))
