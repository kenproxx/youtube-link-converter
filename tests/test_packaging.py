import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from tools.prepare_deno import unpack_verified, parse_checksum


class PackagingTests(unittest.TestCase):
    def test_parses_official_windows_powershell_and_unix_checksums(self):
        digest = '1327356CD63E23D0DA7D11D5F5CA6B45902B1B62EE2DEBD4FBBD0AAD2AAB9786'
        self.assertEqual(parse_checksum('Algorithm : SHA256\r\nHash : ' + digest + '\r\nPath : C:\\deno.zip'), digest.lower())
        self.assertEqual(parse_checksum(digest.lower() + '  deno.zip'), digest.lower())
        for text in ('Algorithm : SHA256', digest + '\n' + '0' * 64):
            with self.assertRaises(ValueError):
                parse_checksum(text)

    def test_extracts_only_expected_binary_after_checksum_validation(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('deno.exe', b'fixture binary')
            z.writestr('../escape.txt', b'untrusted')
        data = buf.getvalue()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'deno.exe'
            with self.assertRaises(ValueError):
                unpack_verified(data, '0' * 64, 'deno.exe', out)
            self.assertFalse(out.exists())
            unpack_verified(data, hashlib.sha256(data).hexdigest(), 'deno.exe', out)
            self.assertEqual(out.read_bytes(), b'fixture binary')
            self.assertEqual(list(Path(tmp).iterdir()), [out])
