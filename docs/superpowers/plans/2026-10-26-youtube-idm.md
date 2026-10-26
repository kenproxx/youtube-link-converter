# YouTube IDM Converter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Windows GUI converter with combined media, quality caps, title filenames, TXT and IDM queue integration.
**Architecture:** Pure conversion helpers plus yt-dlp adapter, threaded Tkinter GUI and Windows one-file packaging.
**Tech Stack:** Python 3.12, Tkinter, yt-dlp with EJS, Deno, PyInstaller.
**Spec:** docs/superpowers/specs/2026-10-26-youtube-idm-design.md

## Global Constraints
- One file must contain audio and video. No merging or media downloads.
- Quality options: best, 360, 480, 720, 1080; never exceed numeric cap.
- Package dependencies inside EXE using build.bat as in facebook-scheduler.
- No push or publication; never claim a Windows artifact was built unless it was.

## Review Focus
- Untrusted URLs and unsupported hostnames: reject, never execute through shell.
- No progressive formats: useful per-video error.
- Windows reserved/duplicate filenames: valid unique title-based names.
- Partial failures and cancellation: preserve successes and keep GUI responsive.
- Missing bundled runtime or IDM: actionable error without downloading at runtime.

### Task 1: Conversion core and tests
Files: app/core.py, app/extractor.py, app/idm.py, tests/test_core.py, tests/test_extractor.py.
Interfaces: parse_urls(text), select_format(info, quality), safe_filename(title, ext), convert_video(url, quality), export_txt(path, results), idm_command(exe, result).
- [ ] Write offline tests for URL validation, quality selection, filename safety, TXT, extraction options and IDM arguments; run and confirm failure.
- [ ] Implement helpers and adapter with finite retries and bundled Deno discovery; rerun complete unittest suite.

### Task 2: GUI
Files: main.py, app/ui.py, README.md.
Interfaces: consume core/extractor/IDM helpers; queue worker messages on main thread.
- [ ] Add multiline TXT input, quality selector, conversion/cancel controls, results table and copy/export/IDM actions.
- [ ] Validate imports, compile and run GUI smoke test if display is supported; document behavior and limitations.

### Task 3: Standalone Windows packaging
Files: build.bat, tools/prepare_deno.py, requirements.txt, requirements-dev.txt, .github/workflows/build-windows.yml, .gitignore.
- [ ] Pin compatible dependencies and Deno release; verify downloaded official Deno checksum before extraction.
- [ ] Build with PyInstaller onefile/windowed and explicit dependency collection + bundled Deno; run offline tests and packaged self-check on Windows.
- [ ] Run available Linux tests and inspect packaging; report Windows build and real IDM/YouTube checks separately if unavailable here.
