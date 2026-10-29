# YouTube Cookie Authentication Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement inline with a final independent review.

**Goal:** Recover from YouTube verification errors using an explicitly selected local browser session or cookie file.

**Architecture:** A small `app/auth.py` owns cookie parsing/loading, in-memory yt-dlp sessions and actionable errors. Extractor/downloader consume it; Tk captures settings before launching its worker.

**Tech Stack:** Existing Python/Tk, yt-dlp, sqlite3 and bundled crypto; no new library.

**Spec:** `docs/superpowers/specs/2026-10-29-youtube-cookie-auth.md`

## Global Constraints

- No browser access by default; no cookie persistence, source-file modification, logging, TXT or IDM credential export.
- Exact selected quality, AV verification and standalone Windows packaging remain required.
- Network policy disallows live YouTube here; report this validation limit.

## Review Focus

- Malformed, expired or unrelated-domain cookie files fail without exposing their contents.
- Browser database lock/decryption failures give a useful fallback.
- Both video/audio transfers retain the metadata authentication session.
- IDM cannot export cookie-bound media, even when yt-dlp records cookies outside headers.
- Tk freezes cookie controls during work and displays bot-recovery instructions.

### Task 1: Authenticated extraction and download

**Files:** New `app/auth.py`, `tests/test_auth.py`; modify extractor/downloader/core and their tests.

**Interfaces:** `CookieSource(browser=None, file=None, profile=None)` and `youtube_session(options, factory, *, auth=None, cookiejar=None)`; add keyword-only `auth=None` to public conversion/download functions.

- [x] Write failing tests for bot error translation, authenticated HTTP transfer, source-file preservation and invalid-file redaction; run them and confirm missing behavior.
- [x] Implement explicit cookie loading with no persistent output, pass the jar across downloads, preserve unauthenticated paths, reject authenticated IDM URLs.
- [x] Run auth/extraction/core/download tests; expected all pass.

### Task 2: User recovery and packaging

**Files:** `app/ui.py`, `tests/test_ui.py`, `main.py`, `build.bat`, README.

**Interfaces:** Tk snapshots `CookieSource` per batch and passes it only when selected; no worker reads Tk variables.

- [x] Add failing Tk tests for source selection, disabled busy controls and visible recovery details.
- [x] Add selector/file picker/profile/help, automatic failed-row details and forwarding to both actions. Update help/docs and validate sqlite3 in packaged self-check.
- [x] Run full suite with Xvfb, pip check, compileall and diff check; build/check Linux frozen diagnostic.
- [x] Independent whole-change review and regression fixes; integrate by pushing the branch and fast-forward merging/pushing main under standing user authorization after final validation.

## Validation and review record

67 Python tests pass with actual Tk under Xvfb, including real Firefox SQLite extraction, real authenticated localhost transfers of both 1080p video/audio streams, FFmpeg merging and cookie-file preservation. `pip check`, `compileall` and `git diff --check` pass. Linux one-file dependency self-check includes Deno, EJS, FFmpeg, Tcl and SQLite; this is not a Windows EXE validation.

The independent reviewer reproduced a partial Chromium cookie jar after warning-only decryption failure. A synthetic Chromium SQLite/v10 regression failed before the fix and passes after it: browser-reader warnings/errors now cause a sanitized Firefox/cookies.txt fallback, with no cookie diagnostics printed. A format-level authentication error also lacked MP4 guidance; its strengthened regression failed before the message fix and passes after it.

Live YouTube is blocked by this cloud's network policy; real Windows cookie decryption and Windows EXE behavior remain for Windows verification. Review also observed an intermittent Tk teardown crash reproduced with the pre-change UI/tests; the full 67-test Xvfb runs here completed successfully. That baseline lifecycle issue is outside this authentication fix.
