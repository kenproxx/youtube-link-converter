import os
import time
import tkinter as tk
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from app.core import ConversionResult
from app.ui import ConverterApp


@unittest.skipUnless(os.environ.get('DISPLAY'), 'GUI smoke test requires a display')
class GuiTests(unittest.TestCase):
    def test_batch_updates_table_and_preserves_failures(self):
        root = tk.Tk()
        root.withdraw()
        def convert(url, quality):
            if url.endswith('123456789_-'):
                raise ValueError('Không có định dạng phù hợp')
            return ConversionResult(url, 'Tên video', 'Tên video.mp4', 'https://media.test/a', 640, width=360)
        try:
            app = ConverterApp(root, converter=convert)
            app.input.insert('1.0', 'https://youtu.be/abcdefghijk\nhttps://youtu.be/123456789_-')
            app.quality.set('360p')
            app.start_conversion()
            deadline = time.monotonic() + 5
            while app.busy and time.monotonic() < deadline:
                root.update()
                time.sleep(.01)
            self.assertFalse(app.busy)
            self.assertEqual(len(app.results), 2)
            self.assertEqual(app.results[0].filename, 'Tên video.mp4')
            self.assertIn('đúng chất lượng', app.table.item('0', 'values')[-1])
            self.assertEqual(app.table.item('0', 'values')[1], '360p (360×640)')
            self.assertIsNotNone(app.results[1].error)
            self.assertEqual(str(app.convert_button['state']), 'normal')
        finally:
            root.destroy()

    def test_wrong_quality_cannot_be_copied_exported_or_sent_to_idm(self):
        root = tk.Tk()
        root.withdraw()
        def convert(url, quality):
            return ConversionResult(url, 'Low', 'Low.mp4', 'https://media.test/low', 360)
        try:
            app = ConverterApp(root, converter=convert)
            app.input.insert('1.0', 'https://youtu.be/abcdefghijk')
            app.quality.set('1080p')
            app.start_conversion()
            deadline = time.monotonic() + 5
            while app.busy and time.monotonic() < deadline:
                root.update()
                time.sleep(.01)
            self.assertFalse(app.busy)
            self.assertIsNotNone(app.results[0].error)
            self.assertFalse(app.results[0].url)
            self.assertEqual(app.chosen_results(), [])
            for button in app.result_buttons:
                self.assertEqual(str(button['state']), 'disabled')
        finally:
            root.destroy()

    def test_download_action_uses_exact_quality_and_keeps_local_files_out_of_url_actions(self):
        root = tk.Tk()
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                def download(url, quality, folder, progress):
                    self.assertEqual(quality, 1080)
                    progress('Đang tải hình 50%')
                    path = Path(folder) / 'Tên video.mp4'
                    path.write_bytes(b'fixture completed download')
                    return ConversionResult(url, 'Tên video', path.name, height=1080,
                                            width=1920, local_path=str(path))
                app = ConverterApp(root, downloader=download)
                app.input.insert('1.0', 'https://youtu.be/abcdefghijk')
                app.quality.set('1080p')
                with patch('app.ui.filedialog.askdirectory', return_value=tmp):
                    app.start_conversion(download=True)
                deadline = time.monotonic() + 5
                while app.busy and time.monotonic() < deadline:
                    root.update()
                    time.sleep(.01)
                self.assertFalse(app.busy)
                self.assertIsNone(app.results[0].error)
                self.assertTrue(Path(app.results[0].local_path).is_file())
                self.assertIn('Đã lưu MP4', app.table.item('0', 'values')[-1])
                self.assertIn(tmp, app.details.get('1.0', 'end'))
                self.assertEqual(app.chosen_results(), [])
                for button in app.result_buttons:
                    self.assertEqual(str(button['state']), 'disabled')
        finally:
            root.destroy()

    def test_destroy_cancels_owned_poll_callbacks(self):
        root = tk.Tk()
        root.withdraw()
        ConverterApp(root)
        pending = set(root.tk.call('after', 'info'))
        self.assertTrue(pending)
        root.destroy()
        remaining = set(root.tk.call('after', 'info'))
        self.assertFalse(pending & remaining, 'Destroyed window left a poll callback in Tcl')
