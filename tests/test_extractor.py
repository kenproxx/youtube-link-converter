import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.extractor import convert_video, extractor_options, find_deno


class ExtractorTests(unittest.TestCase):
    def test_options_disable_remote_code_and_use_explicit_runtime(self):
        opts = extractor_options(Path('/bundle/tools/deno.exe'))
        self.assertEqual(opts['js_runtimes'], {'deno': {'path': '/bundle/tools/deno.exe'}})
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
            result = convert_video('https://www.youtube.com/watch?v=abcdefghijk', 720, FakeYDL)
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
