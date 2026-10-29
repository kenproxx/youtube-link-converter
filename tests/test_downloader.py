import io
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from app.downloader import select_download_formats, download_video, find_ffmpeg, inspect_media


def fmt(fid, height=None, width=None, video='avc1', audio='none', ext='mp4'):
    return dict(format_id=fid, height=height, width=width, vcodec=video, acodec=audio,
                ext=ext, protocol='http', url='http://127.0.0.1/' + fid)


class DownloadSelectionTests(unittest.TestCase):
    def test_1080_video_and_audio_are_selected_instead_of_360_combined(self):
        v, a = select_download_formats({'formats': [fmt('18', 360, audio='mp4a'),
            fmt('137', 1080, 1920), fmt('140', video='none', audio='mp4a', ext='m4a')]}, 1080)
        self.assertEqual((v['format_id'], a['format_id']), ('137', '140'))

    def test_missing_exact_quality_or_audio_is_an_error(self):
        for formats in ([fmt('18', 360, audio='mp4a')], [fmt('137', 1080, 1920)]):
            with self.assertRaises(ValueError):
                select_download_formats({'formats': formats}, 1080)

    def test_portrait_quality_and_best_do_not_depend_on_orientation(self):
        formats = [fmt('portrait', 1920, 1080), fmt('landscape', 1440, 2560),
                   fmt('audio', video='none', audio='mp4a', ext='m4a')]
        self.assertEqual(select_download_formats({'formats': formats}, 1080)[0]['format_id'], 'portrait')
        self.assertEqual(select_download_formats({'formats': formats}, None)[0]['format_id'], 'landscape')

    def test_combined_exact_format_does_not_require_an_extra_audio_stream(self):
        video, audio = select_download_formats({'formats': [fmt('22', 720, 1280, audio='mp4a')]}, 720)
        self.assertEqual(video['format_id'], '22')
        self.assertIsNone(audio)

    def test_rejects_drm_live_and_unsafe_urls(self):
        for changes in ({'has_drm': True}, {'url': 'file:///movie.mp4'}, {'url': 'http://user:pass@x.test/v'}):
            f = fmt('bad', 1080, audio='mp4a')
            f.update(changes)
            with self.assertRaises(ValueError):
                select_download_formats({'formats': [f]}, 1080)
        with self.assertRaises(ValueError):
            select_download_formats({'is_live': True, 'formats': [fmt('x', 1080, audio='mp4a')]}, 1080)


class DownloadIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.ffmpeg = find_ffmpeg()
        flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        for name, inputs, codec in [
            ('video.mp4', ['-f', 'lavfi', '-i', 'color=c=blue:s=1920x1080:r=1'], ['-an', '-c:v', 'libx264', '-preset', 'ultrafast', '-threads', '1']),
            ('low.mp4', ['-f', 'lavfi', '-i', 'color=c=blue:s=640x360:r=1'], ['-an', '-c:v', 'libx264', '-preset', 'ultrafast', '-threads', '1']),
            ('audio.m4a', ['-f', 'lavfi', '-i', 'sine=frequency=440:duration=1'], ['-vn', '-c:a', 'aac'])]:
            subprocess.run([cls.ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', *inputs,
                            '-t', '1', *codec, str(cls.root / name)], check=True, **flags)
        class Handler(SimpleHTTPRequestHandler):
            def log_message(self, *args): pass
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(cls.root)))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}/'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(); cls.tmp.cleanup()

    def info(self):
        v, a = fmt('137', 1080, 1920), fmt('140', video='none', audio='mp4a', ext='m4a')
        v['url'], a['url'] = self.base + 'video.mp4', self.base + 'audio.m4a'
        return {'id': 'abcdefghijk', 'title': 'Tên video', 'extractor': 'youtube',
                'extractor_key': 'Youtube', 'webpage_url': 'https://www.youtube.com/watch?v=abcdefghijk', 'formats': [v, a]}

    def factory(self, opts):
        # Only replace remote YouTube metadata extraction. Transfer/FFmpeg remain real.
        from yt_dlp import YoutubeDL
        info = self.info()
        class LocalMetadataYDL(YoutubeDL):
            def extract_info(self, *args, **kwargs): return info
        return LocalMetadataYDL(opts)

    def test_real_transfer_merge_exact_resolution_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp, patch('app.downloader.find_deno', return_value=Path('/unused/deno')):
            existing = Path(tmp) / 'Tên video.mp4'
            existing.write_bytes(b'keep my existing file')
            messages = []
            result = download_video('https://www.youtube.com/watch?v=abcdefghijk', 1080, tmp,
                                    progress=messages.append, ydl_factory=self.factory)
            self.assertEqual(existing.read_bytes(), b'keep my existing file')
            self.assertEqual(result.filename, 'Tên video (2).mp4')
            self.assertEqual(result.quality, 1080)
            self.assertFalse(result.url)
            self.assertEqual(inspect_media(result.local_path, self.ffmpeg), (1920, 1080))
            self.assertTrue(any('Ghép' in msg for msg in messages))
            self.assertFalse(any(p.name.startswith('.yt-converter-') for p in Path(tmp).iterdir()))

    def test_failure_does_not_publish_or_leave_partial_files(self):
        with tempfile.TemporaryDirectory() as tmp, patch('app.downloader.find_deno', return_value=Path('/unused/deno')):
            with patch('app.downloader.merge_media', side_effect=RuntimeError('fixture merge failure')):
                with self.assertRaisesRegex(RuntimeError, 'fixture merge failure'):
                    download_video('https://www.youtube.com/watch?v=abcdefghijk', 1080, tmp, ydl_factory=self.factory)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_server_returning_lower_resolution_is_rejected_after_merge(self):
        info = self.info()
        info['formats'][0]['url'] = self.base + 'low.mp4'
        with tempfile.TemporaryDirectory() as tmp, patch('app.downloader.find_deno', return_value=Path('/unused/deno')):
            with patch.object(self, 'info', return_value=info):
                with self.assertRaisesRegex(ValueError, '1080p'):
                    download_video('https://www.youtube.com/watch?v=abcdefghijk', 1080, tmp, ydl_factory=self.factory)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_missing_hls_fragment_is_fatal_and_never_publishes_partial_mp4(self):
        command = [self.ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'lavfi', '-i', 'color=c=blue:s=1920x1080:r=1:d=3',
            '-f', 'lavfi', '-i', 'sine=frequency=440:duration=3',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-threads', '1', '-g', '1', '-c:a', 'aac',
            '-f', 'hls', '-hls_time', '1', '-hls_playlist_type', 'vod', '-hls_segment_type', 'fmp4',
            '-hls_segment_filename', str(self.root / 'part%d.m4s'), str(self.root / 'playlist.m3u8')]
        subprocess.run(command, check=True, **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}))
        (self.root / 'part1.m4s').unlink()
        info = self.info()
        combined = fmt('hls', 1080, 1920, audio='mp4a')
        combined.update(protocol='m3u8_native', url=self.base + 'playlist.m3u8')
        info['formats'] = [combined]
        with tempfile.TemporaryDirectory() as tmp, patch('app.downloader.find_deno', return_value=Path('/unused/deno')):
            with patch.object(self, 'info', return_value=info):
                with self.assertRaises(Exception):
                    download_video('https://www.youtube.com/watch?v=abcdefghijk', 1080, tmp, ydl_factory=self.factory)
            self.assertEqual(list(Path(tmp).iterdir()), [])
