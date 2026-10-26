"""Download pinned official Deno, validate published SHA-256, bundle at build time."""
import argparse
import hashlib
import io
from pathlib import Path
import re
import sys
import zipfile

if __package__:
    from .download_progress import fetch_bytes
else:
    from download_progress import fetch_bytes

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


def prepare(target, *, project_root=None, stream=None):
    stream = sys.stdout if stream is None else stream
    root = Path(project_root) if project_root is not None else Path(__file__).resolve().parent.parent
    asset, member = TARGETS[target]
    base = f'https://github.com/denoland/deno/releases/download/v{DENO_VERSION}/{asset}'
    print(f'[Deno] Preparing version {DENO_VERSION} for {target}', file=stream, flush=True)
    checksum = parse_checksum(fetch_bytes(base + '.sha256sum', 'Deno checksum', stream=stream).decode('utf-8-sig'))
    cache = root / '.build-tools' / 'downloads' / f'deno-{DENO_VERSION}-{asset}'
    data = cache.read_bytes() if cache.is_file() else None
    if data is not None and hashlib.sha256(data).hexdigest() == checksum:
        print('[Deno] Using verified cached archive; no asset download needed.', file=stream, flush=True)
    else:
        if data is not None:
            print('[Deno] Cached archive failed checksum; downloading a fresh copy.', file=stream, flush=True)
        data = fetch_bytes(base, 'Deno archive', stream=stream)
    print('[Deno] Checking archive SHA-256...', file=stream, flush=True)
    if hashlib.sha256(data).hexdigest() != checksum:
        raise ValueError('Deno SHA-256 mismatch: refusing to use downloaded archive')
    print('[Deno] SHA-256 verified. Extracting runtime...', file=stream, flush=True)
    output = root / 'tools' / member
    unpack_verified(data, checksum, member, output)
    temporary_cache = cache.with_suffix('.zip.part')
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        temporary_cache.write_bytes(data)
        temporary_cache.replace(cache)
    except OSError as exc:
        print(f'[Deno] Runtime ready, but archive cache could not be saved: {exc}', file=stream, flush=True)
        try:
            temporary_cache.unlink(missing_ok=True)
        except OSError:
            pass
    print(f'[Deno] Ready: {output}', file=stream, flush=True)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', choices=TARGETS, default='windows' if sys.platform == 'win32' else 'linux')
    try:
        prepare(parser.parse_args().target)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        parser.exit(1, f'DENO SETUP FAILED: {exc}. Check access to GitHub and rerun build.bat.\n')
    except KeyboardInterrupt:
        parser.exit(130, 'Deno setup cancelled. No unverified archive was installed.\n')
