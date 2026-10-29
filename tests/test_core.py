import tempfile
import unittest
from pathlib import Path
from threading import Event

from app.core import (parse_urls, select_format, safe_filename, unique_filename,
                      export_txt, run_batch, ConversionResult)
from app.idm import idm_command


def media(fid, height, **extra):
    return dict(format_id=fid, height=height, ext='mp4', vcodec='avc1',
                acodec='mp4a', protocol='https', url=f'https://media.example/{fid}', **extra)


class UrlTests(unittest.TestCase):
    def test_normalizes_and_deduplicates_video_ids(self):
        urls, errors = parse_urls('https://youtu.be/abcdefghijk\n'
            'https://www.youtube.com/watch?v=abcdefghijk&list=PL123\n'
            'https://youtube.com/shorts/123456789_-\n')
        self.assertEqual(urls, ['https://www.youtube.com/watch?v=abcdefghijk',
                                'https://www.youtube.com/watch?v=123456789_-'])
        self.assertEqual(errors, [])

    def test_rejects_fake_hosts_credentials_playlist_and_bad_id(self):
        for url in ['https://youtube.com.evil.org/watch?v=abcdefghijk',
                    'https://user:pass@youtube.com/watch?v=abcdefghijk',
                    'https://youtube.com/playlist?list=abc', 'file:///etc/passwd',
                    'https://youtu.be/too-short', 'https://youtube.com:443/watch?v=abcdefghijk']:
            with self.subTest(url=url):
                urls, errors = parse_urls(url)
                self.assertEqual(urls, [])
                self.assertEqual(len(errors), 1)

    def test_accepts_utf8_bom_and_blank_lines(self):
        urls, errors = parse_urls('\ufeff\nhttps://youtu.be/abcdefghijk\n\n')
        self.assertEqual(len(urls), 1)
        self.assertEqual(errors, [])


class FormatTests(unittest.TestCase):
    def test_exact_quality_and_best_rank_resolution_before_container(self):
        formats = [media('360', 360), media('720', 720), media('1080', 1080)]
        self.assertEqual(select_format({'formats': formats}, 720)['format_id'], '720')
        self.assertEqual(select_format({'formats': formats}, None)['format_id'], '1080')
        formats[1]['ext'] = 'webm'
        self.assertEqual(select_format({'formats': formats}, 720)['format_id'], '720')

    def test_prefers_mp4_when_resolution_tied(self):
        formats = [media('webm', 720), media('mp4', 720)]
        formats[0]['ext'] = 'webm'
        self.assertEqual(select_format({'formats': formats}, 720)['format_id'], 'mp4')

    def test_lower_higher_and_unknown_quality_are_all_rejected(self):
        for f in [media('360', 360), media('720', 720), media('unknown', None)]:
            with self.assertRaises(ValueError):
                select_format({'formats': [f]}, 480)

    def test_rejects_separate_streams_manifests_and_missing_codecs(self):
        variants = [dict(acodec='none'), dict(vcodec='none'), dict(acodec=None),
                    dict(protocol='m3u8_native'), dict(url='https://x.test/master.m3u8'),
                    dict(url='file:///movie.mp4'), dict(has_drm=True)]
        for changes in variants:
            f = media('bad', 720)
            f.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                select_format({'formats': [f]}, None)

    def test_rejects_authenticated_formats(self):
        for headers in [{'Cookie': 'secret'}, {'authorization': 'Bearer secret'}]:
            f = media('bad', 360, http_headers=headers)
            with self.assertRaises(ValueError):
                select_format({'formats': [f]}, None)
        f = media('bad', 360)
        with self.assertRaises(ValueError):
            select_format({'formats': [f], 'http_headers': {'Cookie': 'secret'}}, None)

    def test_accepts_raw_youtube_progressive_format_without_protocol(self):
        f = media('18', 360)
        del f['protocol']
        self.assertEqual(select_format({'formats': [f]}, 360)['format_id'], '18')

    def test_rejects_custom_headers_that_idm_cannot_forward(self):
        f = media('360', 360, http_headers={'X-Custom-Token': 'needed'})
        with self.assertRaises(ValueError):
            select_format({'formats': [f]}, None)

    def test_rejects_active_live_stream(self):
        with self.assertRaises(ValueError):
            select_format({'is_live': True, 'formats': [media('360', 360)]}, None)

    def test_1080_never_falls_back_to_360_even_with_only_silent_1080(self):
        silent = media('137', 1080)
        silent['acodec'] = 'none'
        with self.assertRaises(ValueError) as raised:
            select_format({'formats': [media('18', 360), silent]}, 1080)
        self.assertIn('1080p', str(raised.exception))
        self.assertIn('360p', str(raised.exception))
        self.assertIn('ghép', str(raised.exception))

    def test_portrait_1080_uses_the_shorter_dimension(self):
        portrait = media('portrait', 1920, width=1080)
        self.assertEqual(select_format({'formats': [portrait]}, 1080)['format_id'], 'portrait')
        with self.assertRaises(ValueError):
            select_format({'formats': [media('low', 640, width=360)]}, 1080)

    def test_best_compares_landscape_and_portrait_fairly(self):
        formats = [media('portrait', 1920, width=1080), media('landscape', 1440, width=2560)]
        self.assertEqual(select_format({'formats': formats}, None)['format_id'], 'landscape')

    def test_invalid_quality_rejected(self):
        with self.assertRaises(ValueError):
            select_format({'formats': [media('360', 360)]}, -1)


class FilenameTests(unittest.TestCase):
    def test_preserves_title_and_removes_windows_special_chars(self):
        self.assertEqual(safe_filename('Bài hát: "Xin/chào"?*', 'mp4'), 'Bài hát_ _Xin_chào___.mp4')

    def test_reserved_names_trailing_dots_and_long_unicode(self):
        self.assertEqual(safe_filename('CON', 'mp4'), '_CON.mp4')
        self.assertEqual(safe_filename('NUL.txt', 'mp4'), '_NUL.txt.mp4')
        self.assertEqual(safe_filename('hello...  ', 'webm'), 'hello.webm')
        self.assertLessEqual(len(safe_filename('🎵' * 300, 'mp4').encode('utf-16-le')) // 2, 180)
        self.assertEqual(safe_filename('', 'mp4'), 'video.mp4')
        self.assertEqual(safe_filename('../evil', '../../bat'), '.._evil.mp4')

    def test_windows_device_aliases_and_spaces_before_extension(self):
        for title, expected in [('CON .txt', '_CON .txt.mp4'), ('conin$', '_conin$.mp4'),
                                ('CONOUT$', '_CONOUT$.mp4'), ('COM1 .video', '_COM1 .video.mp4')]:
            with self.subTest(title=title):
                self.assertEqual(safe_filename(title, 'mp4'), expected)

    def test_case_insensitive_collision_suffixes(self):
        used = set()
        self.assertEqual(unique_filename('Song.mp4', used), 'Song.mp4')
        self.assertEqual(unique_filename('song.mp4', used), 'song (2).mp4')
        self.assertEqual(unique_filename('song.mp4', used), 'song (3).mp4')


class BatchTests(unittest.TestCase):
    def test_partial_failure_does_not_discard_success(self):
        def convert(url, quality):
            if url == 'bad':
                raise ValueError('Không có định dạng phù hợp')
            return ConversionResult(url, 'Tên bài', 'song.mp4', 'https://x.test/a', 720)
        events = list(run_batch(['ok', 'bad', 'ok2'], 720, Event(), convert))
        self.assertEqual([e.error is None for e in events], [True, False, True])
        self.assertEqual([events[0].filename, events[2].filename], ['song.mp4', 'song (2).mp4'])

    def test_batch_rejects_converter_results_with_wrong_or_unknown_quality(self):
        for height in (360, 720, 1440, None):
            with self.subTest(height=height):
                def convert(url, quality):
                    return ConversionResult(url, 'x', 'x.mp4', 'https://x.test/a', height)
                result = list(run_batch(['a'], 1080, Event(), convert))[0]
                self.assertIsNotNone(result.error)
                self.assertFalse(result.url)
                with tempfile.TemporaryDirectory() as tmp:
                    output = Path(tmp) / 'links.txt'
                    export_txt(output, [result])
                    self.assertEqual(output.read_text(), '')

    def test_cancel_stops_before_next_video(self):
        cancel = Event()
        def convert(url, quality):
            cancel.set()
            return ConversionResult(url, 'x', 'x.mp4', 'https://x.test/a', 360)
        self.assertEqual(len(list(run_batch(['a', 'b'], None, cancel, convert))), 1)

    def test_txt_exports_only_successes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'links.txt'
            results = [ConversionResult('a', 'A', 'A.mp4', 'https://x.test/a?k=1&n=2', 360),
                       ConversionResult('b', error='bad')]
            export_txt(path, results)
            self.assertEqual(path.read_bytes(), b'https://x.test/a?k=1&n=2\n')

    def test_idm_arguments_preserve_filename_and_url_without_shell(self):
        r = ConversionResult('a', 'A', 'Bài hát & video.mp4', 'https://x.test/a?k=1&n=2', 720)
        self.assertEqual(idm_command('C:/Program Files/IDM/IDMan.exe', r),
                         ['C:/Program Files/IDM/IDMan.exe', '/d', 'https://x.test/a?k=1&n=2',
                          '/f', 'Bài hát & video.mp4', '/a'])
        with self.assertRaises(ValueError):
            idm_command('IDMan.exe', ConversionResult('a', error='bad'))
