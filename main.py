"""GUI entry point and headless packaged-dependency verification."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def self_check(output):
    try:
        import tkinter
        import yt_dlp.version
        import yt_dlp_ejs
        from importlib.resources import files
        from app.extractor import find_deno
        from app.downloader import find_ffmpeg
        ffmpeg = find_ffmpeg()
        deno = find_deno()
        flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {}
        version = subprocess.check_output([str(deno), '--version'], text=True, timeout=20, **flags)
        ffmpeg_version = subprocess.check_output([ffmpeg, '-version'], text=True, timeout=20, **flags)
        solver = files('yt_dlp_ejs').joinpath('yt', 'solver', 'core.min.js')
        library = files('yt_dlp_ejs').joinpath('yt', 'solver', 'lib.min.js')
        if not solver.is_file() or not library.is_file():
            raise RuntimeError('Missing bundled yt-dlp EJS solver files')
        # Tcl initialization checks packaged Tcl data without requiring a display.
        tcl = tkinter.Tcl()
        if sys.platform == 'win32' or os.environ.get('DISPLAY'):
            root = tkinter.Tk()
            try:
                root.withdraw()
                root.update_idletasks()
            finally:
                root.destroy()
        result = {'ok': True, 'yt_dlp': yt_dlp.version.__version__,
                  'deno': version.splitlines()[0], 'ffmpeg': ffmpeg_version.splitlines()[0], 'tcl': tcl.eval('info patchlevel'),
                  'frozen': bool(getattr(sys, 'frozen', False))}
        code = 0
    except Exception as exc:
        result, code = {'ok': False, 'error': str(exc)}, 1
    Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-check', metavar='JSON_FILE', help='verify bundled dependencies without opening a window')
    args = parser.parse_args()
    if args.self_check:
        return self_check(args.self_check)
    import tkinter as tk
    from app.ui import ConverterApp
    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
