@echo off
setlocal
cd /d "%~dp0"

rem Build machine needs Python 3.12 x64. End users only need the resulting EXE.
if not exist .build-venv\Scripts\python.exe (
  where py >nul 2>nul
  if errorlevel 1 (
    python -m venv .build-venv
  ) else (
    py -3.12 -m venv .build-venv
  )
  if errorlevel 1 goto :error
)
set "BUILD_PY=%CD%\.build-venv\Scripts\python.exe"
"%BUILD_PY%" -c "import sys,struct; assert sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8, 'Build requires Python 3.12 x64'"
if errorlevel 1 goto :error
"%BUILD_PY%" -m pip install -r requirements-dev.txt
if errorlevel 1 goto :error
"%BUILD_PY%" -m unittest discover -v
if errorlevel 1 goto :error

echo [1/3] Downloading and verifying official Deno runtime...
"%BUILD_PY%" tools\prepare_deno.py --target windows
if errorlevel 1 goto :error
tools\deno.exe --version
if errorlevel 1 goto :error

echo [2/3] Building standalone YouTubeLinkConverter.exe...
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
  --add-binary "tools\deno.exe;tools" ^
  main.py
if errorlevel 1 goto :error

echo [3/3] Checking dependencies from the packaged executable...
if exist dist\self-check.json del dist\self-check.json
start "" /wait "dist\YouTubeLinkConverter.exe" --self-check "%CD%\dist\self-check.json"
if errorlevel 1 goto :error
"%BUILD_PY%" -c "import json; d=json.load(open('dist/self-check.json', encoding='utf-8')); assert d['ok'] and d['frozen'], d; print(d)"
if errorlevel 1 goto :error

echo DONE: dist\YouTubeLinkConverter.exe
echo Python, Tk, yt-dlp, EJS and Deno are bundled. No runtime install is needed.
if /I not "%~1"=="--ci" pause
exit /b 0

:error
echo BUILD FAILED. Read the error above.
if /I not "%~1"=="--ci" pause
exit /b 1
