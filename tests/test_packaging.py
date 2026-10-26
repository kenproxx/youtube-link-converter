import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from tools.prepare_deno import unpack_verified, parse_checksum, prepare


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


class DenoPreparationTests(unittest.TestCase):
    def test_verified_archive_is_cached_and_next_build_skips_asset_download(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('deno.exe', b'verified runtime')
        data = buf.getvalue()
        digest = hashlib.sha256(data).hexdigest().encode()
        def download(url, label, **kw):
            return digest if url.endswith('.sha256sum') else data
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with patch('tools.prepare_deno.fetch_bytes', side_effect=download):
                path = prepare('windows', project_root=Path(tmp), stream=output)
            self.assertEqual(path.read_bytes(), b'verified runtime')
            self.assertIn('SHA-256 verified', output.getvalue())
            self.assertIn('Extracting', output.getvalue())
            def checksum_only(url, label, **kw):
                if not url.endswith('.sha256sum'):
                    raise AssertionError('Verified cache must avoid the asset download')
                return digest
            with patch('tools.prepare_deno.fetch_bytes', side_effect=checksum_only):
                again = prepare('windows', project_root=Path(tmp), stream=output)
            self.assertEqual(again.read_bytes(), b'verified runtime')
            self.assertIn('Using verified cached archive', output.getvalue())

    def test_bad_download_keeps_existing_runtime_and_does_not_cache_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / 'tools' / 'deno.exe'
            output.parent.mkdir()
            output.write_bytes(b'previous verified runtime')
            def download(url, label, **kw):
                return b'0' * 64 if url.endswith('.sha256sum') else b'corrupt'
            with patch('tools.prepare_deno.fetch_bytes', side_effect=download):
                with self.assertRaises(ValueError):
                    prepare('windows', project_root=root, stream=io.StringIO())
            self.assertEqual(output.read_bytes(), b'previous verified runtime')
            self.assertEqual(list(root.rglob('*.zip')), [])
