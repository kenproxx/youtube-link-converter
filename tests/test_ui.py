import os
import time
import tkinter as tk
import unittest
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
            return ConversionResult(url, 'Tên video', 'Tên video.mp4', 'https://media.test/a', 360)
        try:
            app = ConverterApp(root, converter=convert)
            app.input.insert('1.0', 'https://youtu.be/abcdefghijk\nhttps://youtu.be/123456789_-')
            app.quality.set('720p')
            app.start_conversion()
            deadline = time.monotonic() + 5
            while app.busy and time.monotonic() < deadline:
                root.update()
                time.sleep(.01)
            self.assertFalse(app.busy)
            self.assertEqual(len(app.results), 2)
            self.assertEqual(app.results[0].filename, 'Tên video.mp4')
            self.assertIn('thấp hơn', app.table.item('0', 'values')[-1])
            self.assertIsNotNone(app.results[1].error)
            self.assertEqual(str(app.convert_button['state']), 'normal')
        finally:
            root.destroy()
