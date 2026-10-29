@echo off
setlocal
cd /d "%~dp0"

echo [1/6] Preparing Python build environment...
rem Check the interpreter, not just whether the py launcher exists.
rem If Python is missing, bootstrap verifies and installs official Python locally.
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\bootstrap_windows.ps1" -RepoRoot "%CD%"
if errorlevel 1 goto :error
set "BUILD_PY=%CD%\.build-venv\Scripts\python.exe"
"%BUILD_PY%" -c "import sys,struct; assert sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8, 'Build requires Python 3.12 x64'"
if errorlevel 1 goto :error
echo [2/6] Installing Python build libraries (pip progress below)...
"%BUILD_PY%" -m pip install --progress-bar on --timeout 30 --retries 2 -r requirements-dev.txt
if errorlevel 1 goto :error
echo [3/6] Running application checks...
"%BUILD_PY%" -m unittest discover -v
if errorlevel 1 goto :error

echo [4/6] Downloading and verifying official Deno runtime...
"%BUILD_PY%" -u tools\prepare_deno.py --target windows
if errorlevel 1 goto :error
tools\deno.exe --version
if errorlevel 1 goto :error

echo [5/6] Building standalone YouTubeLinkConverter.exe...
"%BUILD_PY%" -m PyInstaller ^
  --noconfirm --clean --onefile --windowed ^
  --name YouTubeLinkConverter ^
  --collect-all yt_dlp ^
  --collect-all yt_dlp_ejs ^
  --collect-all certifi ^
  --collect-all requests ^
  --collect-all urllib3 ^
  --collect-all websockets ^
  --collect-all Cryptodome ^
  --collect-all brotli ^
  --collect-all mutagen ^
  --collect-all imageio_ffmpeg ^
  --hidden-import sqlite3 ^
  --add-binary "tools\deno.exe;tools" ^
  main.py
if errorlevel 1 goto :error

echo [6/6] Checking dependencies from the packaged executable...
if exist dist\self-check.json del dist\self-check.json
start "" /wait "dist\YouTubeLinkConverter.exe" --self-check "%CD%\dist\self-check.json"
if errorlevel 1 goto :error
"%BUILD_PY%" -c "import json; d=json.load(open('dist/self-check.json', encoding='utf-8')); assert d['ok'] and d['frozen'], d; print(d)"
if errorlevel 1 goto :error

echo DONE: dist\YouTubeLinkConverter.exe
echo Python, Tk, yt-dlp, EJS, Deno and FFmpeg are bundled. No runtime install is needed.
if /I not "%~1"=="--ci" pause
exit /b 0

:error
echo BUILD FAILED. Read the error above.
if /I not "%~1"=="--ci" pause
exit /b 1
