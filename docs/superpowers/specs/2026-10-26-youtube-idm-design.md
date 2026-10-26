# YouTube Link Converter for IDM

## Intent and requirements
Build a Windows desktop executable that converts a list of YouTube video URLs into direct download URLs using yt-dlp. The user requires one media file containing both video and audio, with the YouTube video title as the filename, plus optional TXT export.

## Approach
Recommended: Python 3.12, Tkinter GUI, yt-dlp Python API, PyInstaller one-file Windows build. This gives a small maintainable desktop app with no local web server. An Electron wrapper adds an unnecessary JavaScript runtime; a command-line-only tool makes batch review and export less convenient. The GUI choice is proposed by the implementer, pending approval.

## Interface and flow
Vietnamese labels. Multiline input accepts one YouTube video URL per line and can import UTF-8 TXT. Normalize supported YouTube watch, shorts, live, embed and youtu.be URLs; ignore duplicate video IDs; report malformed lines. Do not expand playlists implicitly.

Convert on a worker thread and report per-video success or failure in a table (title, format/resolution, filename, status). Keep successful results if another video fails. Permit cancellation between videos. Disable conflicting actions while converting.

Choose the best directly downloadable HTTP(S) progressive format containing both video and audio; rank MP4 ahead of other containers, then descending height, bitrate and format ID for deterministic selection. Set network socket timeout to 20 seconds and retries to 1. Exclude manifests and separate audio/video formats. Never silently return a video-only link. Do not download or merge media. If no combined format exists, explain that limitation for that video.

Sanitize the YouTube title into a valid Windows filename, preserve Unicode, handle reserved names, trailing dots/spaces and a 180-character filename limit (including extension), and use the real media extension. Resolve duplicate names in the current batch.

Copy successful URLs; export successful URLs as UTF-8 TXT, one per line. TXT URLs alone cannot enforce filenames in IDM. Do not add another export format in this version.

Provide an explicit Add to IDM action and an IDM executable picker. Find conventional Windows IDM installation paths when present. Invoke IDM using an argument list (never a shell) with /d URL /f filename /a; queue items and let the user start the queue in IDM. Do not launch downloads automatically during conversion. Reject results that require Cookie or Authorization headers that the IDM integration cannot transfer. For other extractor headers use only the configured standard browser user agent and YouTube referer; explain that IDM may still require these values. The /f argument supplies the sanitized video-title filename; remote headers can still influence IDM behavior and require Windows validation.

## Packaging and validation
Bundle yt-dlp with its default challenge-solving dependencies using PyInstaller on Windows. Bundle a supported Deno runtime alongside the frozen application and pass its explicit location to yt-dlp; obtain Windows runtime assets from official releases with published checksum verification. Keep runtime and yt-dlp versions pinned in the build. Validate availability before converting. Add a Windows GitHub Actions build that runs tests and uploads the EXE as an artifact, plus a local PowerShell build script. Do not publish or push without authorization. The target deliverable is an actual Windows EXE. Build scripts or CI YAML alone do not satisfy delivery: if no Windows build executor is accessible from this task, explicitly report EXE creation and clean-Windows verification as blocked rather than claiming completion.

Test parsing, combined-format filtering, filename handling, partial batch failures, TXT output and IDM command construction offline. Smoke-test the GUI when a display is available. Test live YouTube extraction only if network policy permits it. The current Linux host cannot natively validate a Windows EXE; report unrun checks honestly.

## Constraints and limits
Direct links expire and can depend on the extraction IP, cookies and request headers. IDM downloads are best attempted on the same Windows machine/network where conversion occurs. Do not promise IDM compatibility for every YouTube video. No credentials are embedded or requested in chat. Cookie/login support, playlist expansion, separate-stream merging and automatic media downloading are outside this initial version.

## Builder decisions
Keep GUI code separate from conversion and Windows integration. Use dependency injection at the extractor/process boundary for offline tests. Choose current compatible dependency versions after inspecting package metadata. Preserve all user files.
