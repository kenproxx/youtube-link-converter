"""Windows IDM integration: argv only, never shell interpolation."""
import os
from pathlib import Path
import subprocess


def idm_command(exe, result):
    if result.error or not result.url or not result.filename:
        raise ValueError('Không thể thêm kết quả lỗi vào IDM.')
    return [str(exe), '/d', result.url, '/f', result.filename, '/a']


def find_idm():
    for key in ('ProgramFiles(x86)', 'ProgramFiles'):
        root = os.environ.get(key)
        if root:
            path = Path(root) / 'Internet Download Manager' / 'IDMan.exe'
            if path.is_file():
                return str(path)
    return ''


def enqueue(exe, result):
    if os.name != 'nt':
        raise RuntimeError('Chức năng IDM cần Windows.')
    if not Path(exe).is_file():
        raise ValueError('Hãy chọn file IDMan.exe đã cài trên máy.')
    subprocess.run(idm_command(exe, result), check=True, timeout=20,
                   creationflags=subprocess.CREATE_NO_WINDOW)
