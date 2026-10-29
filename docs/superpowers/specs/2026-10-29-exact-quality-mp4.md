# Exact quality and automatic MP4 download

The user requires numeric quality choices to match exactly; no lower/higher/unknown fallback. They chose automatic download of separate video/audio streams and merging to MP4. This supersedes the original quality ceiling and link-only restriction for the new download action; IDM/TXT link conversion remains separate.

Use yt-dlp's resolution convention (shorter dimension): 1920x1080 and 1080x1920 both represent 1080p. Keep original dimensions for display. Best remains an explicit automatic choice. A failure must not expose a wrong-quality URL or file.

Approaches: a single direct URL still needs a progressive AV format; exporting split URLs leaves manual work; the user selected app-controlled download and FFmpeg merge. Add a distinct Vietnamese Download MP4 action and directory picker. Extract metadata once, select exact video and compatible audio (prefer AVC/MP4 and AAC), download only the selected formats, then remux video without scaling/re-encoding. Encode audio to AAC only when needed for MP4. Validate output AV streams and resolution before publishing a title-based filename. Do not overwrite existing files, keep temporary downloads isolated and clean them on failure.

Bundle FFmpeg through pinned imageio-ffmpeg wheel data, collect it in PyInstaller and exercise it in packaged self-check. No end-user library/runtime installation. Show per-stream bytes/progress and merge elapsed status via main-thread queue. Stop after current video; defer window close until owned work ends. Local file results are not exported as direct URLs or sent to IDM.

Verification: strict quality tests, portrait dimensions, missing audio/no exact source, real localhost media transfer plus FFmpeg merge/probe, output collision/failure cleanup, GUI tests and packaged dependency checks. Public YouTube requests are currently outside cloud network allowlist, so live YouTube and Windows behavior must be reported separately. No upscaling or promise that every source has 1080p.
