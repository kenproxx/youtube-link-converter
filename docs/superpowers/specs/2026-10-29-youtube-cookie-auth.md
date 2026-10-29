# YouTube verification recovery

The reported error is YouTube's `Sign in to confirm you're not a bot` response. The application currently has no cookie input. Use yt-dlp's supported browser/file authentication rather than changing quality, spoofing clients, or repeatedly retrying a rejected session.

Add an explicit session-only cookie selector: none (default), Firefox, Chrome, Edge, or Netscape cookies.txt. An optional browser profile name/path supports non-default profiles. Never read browser cookies until the user selects that source and starts work. Filter loaded cookies to YouTube/media domains, keep them in memory, and never overwrite the source cookie file or export credentials. Share the same in-memory cookie jar across metadata and both media downloads. Browser decryption/locked-database failures explain using Firefox or an exported file; invalid/expired/empty files produce a local error without showing cookie values.

Both existing actions use the chosen authentication. MP4 downloads may use authenticated media through yt-dlp. IDM/TXT remain URL-only: reject media requiring cookies/Authorization rather than leaking credentials or promising a portable authenticated URL. Exact-quality selection, packaged dependencies, filenames and newline-only TXT remain as before.

Show a concise Vietnamese recovery message for bot verification, select the failed row so the instructions are visible, and provide an in-app help dialog with official yt-dlp cookie documentation. Cookies may not resolve an IP/session restriction; do not promise success or automatic CAPTCHA solving. Windows Chromium may block cookie decryption; document the fallback. No new runtime dependency is needed (sqlite3 and existing crypto support must be included and checked in the EXE).

Verification uses synthetic cookies only, real yt-dlp cookie requests over local HTTP, actual Tk under Xvfb, the existing full suite and a frozen dependency check. Live YouTube and Windows browser decryption are outside this environment's access/platform.
