# Exact Quality MP4 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline; preserve this isolated cloud checkout.

**Goal:** exact numeric quality and automatic split-stream MP4 download.
**Architecture:** core selection rules, downloader adapter with bundled FFmpeg, threaded existing Tk GUI.
**Tech Stack:** Python 3.12, yt-dlp, Tkinter, imageio-ffmpeg, PyInstaller.
**Spec:** docs/superpowers/specs/2026-10-29-exact-quality-mp4.md

## Global Constraints
No numeric fallback or upscaling; preserve titles and existing files; local downloads never enter URL exports; all end-user dependencies bundled.

## Review Focus
Portrait resolution, absent audio, malicious/expired URLs, existing output filenames, cleanup on download/merge error and orderly shutdown.

### Task 1: Exact quality
- [x] RED tests for strict selection, portrait dimensions, batch guard and export rejection.
- [x] Implement core/extractor/UI quality changes; existing suites pass (GUI rerun passed).

### Task 2: MP4 download
- [x] Test split selection, no lower-resolution fallback, no audio and real media merge through local HTTP.
- [x] Implement select_download_formats and download_video in app/downloader.py; isolated temporary files, bundled FFmpeg, no-overwrite publication, output verification.
- [x] Add GUI action/progress/local-file result handling, update packaging/self-check/dependencies.
- [x] Run complete tests including actual GUI and local media integration; document unrun Windows/live YouTube checks.
- [x] Fresh code review; fixed missing-fragment success bug with strict fragment mode and a failing-then-passing real HLS test. GUI callback teardown also tested RED→GREEN. Commit/push follows final validation.

Validation: 55 tests passed including actual GUI, HTTP media download, 1080p FFmpeg merge, server-quality mismatch and missing HLS segment rejection. Linux one-file build and bundled Deno/FFmpeg self-check passed. Actual Windows build and live YouTube downloads remain unverified.
