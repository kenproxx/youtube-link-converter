import json
import os
from pathlib import Path
import tempfile
import unittest
import tkinter
import subprocess
from unittest.mock import patch

from main import self_check


class SelfCheckTests(unittest.TestCase):
    def test_missing_tk_resources_fail_the_packaged_check(self):
        # Simulate the external Tk installation/resource boundary, not app logic.
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'check.json'
            real_tcl = tkinter.Tcl()
            real_output = subprocess.check_output
            def output_or_version(args, *a, **kw):
                if args == [str(Path('/fake/deno')), '--version']:
                    return 'deno 2.5.6\n'
                return real_output(args, *a, **kw)
            with patch('app.extractor.find_deno', return_value=Path('/fake/deno')), \
                 patch('subprocess.check_output', side_effect=output_or_version), \
                 patch.dict(os.environ, {'DISPLAY': ':test'}), \
                 patch('tkinter.Tcl', return_value=real_tcl), \
                 patch('tkinter.Tk', side_effect=RuntimeError('Missing Tk resources')):
                code = self_check(output)
            self.assertEqual(code, 1)
            data = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(data['error'], 'Missing Tk resources')
            self.assertFalse(data['ok'])
