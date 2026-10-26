"""Download pinned official Deno, validate published SHA-256, bundle at build time."""
import argparse
import hashlib
import io
from pathlib import Path
import re
import sys
from urllib.request import urlopen
import zipfile

DENO_VERSION = '2.5.6'
TARGETS = {'windows': ('deno-x86_64-pc-windows-msvc.zip', 'deno.exe'),
           'linux': ('deno-x86_64-unknown-linux-gnu.zip', 'deno')}


def parse_checksum(text):
    # Windows publishes PowerShell Get-FileHash output; Unix uses sha256sum.
    hashes = re.findall(r'(?<![A-Za-z0-9])[a-fA-F0-9]{64}(?![A-Za-z0-9])', text)
    if len(hashes) != 1:
        raise ValueError('Expected exactly one SHA-256 in official Deno checksum file')
    return hashes[0].lower()


def unpack_verified(data, expected, member, output):
    if not re.fullmatch(r'[a-fA-F0-9]{64}', expected) or hashlib.sha256(data).hexdigest() != expected.lower():
        raise ValueError('Deno SHA-256 mismatch: refusing to use downloaded archive')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        # Never extract arbitrary paths from the downloaded archive.
        binary = archive.read(member)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix('.download')
    temp.write_bytes(binary)
    temp.chmod(0o755)
    temp.replace(output)


def prepare(target):
    asset, member = TARGETS[target]
    base = f'https://github.com/denoland/deno/releases/download/v{DENO_VERSION}/{asset}'
    with urlopen(base + '.sha256sum', timeout=60) as response:
        checksum = parse_checksum(response.read().decode('utf-8-sig'))
    with urlopen(base, timeout=60) as response:
        data = response.read()
    output = Path(__file__).resolve().parent / member
    unpack_verified(data, checksum, member, output)
    print(f'Verified Deno {DENO_VERSION} for {target}: {output.name}')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', choices=TARGETS, default='windows' if sys.platform == 'win32' else 'linux')
    prepare(parser.parse_args().target)
