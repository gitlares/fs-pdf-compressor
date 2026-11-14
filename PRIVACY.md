# Privacy

FS PDF Compressor processes PDF files entirely on the user's computer on
macOS, Windows and Linux.

## Documents and usage data

- No files or file contents are uploaded.
- No account is required.
- No analytics, telemetry or crash-reporting service is included.
- No usage history is collected.

The application invokes the bundled Ghostscript executable locally and writes
the compressed PDF to the location selected by the user.

## Network access

PDF compression does not require a network connection. Network access is
limited to software updates and links explicitly opened by the user:

- On macOS, Sparkle periodically reads the public update feed hosted on GitHub
  Pages and can download signed update archives from GitHub Releases.
- Windows installer builds with WinSparkle ask whether to check for updates
  automatically. If enabled, they periodically read a public GitHub Pages feed.
  **Check for Updates…** also checks that feed on request. Accepted updates are
  downloaded from GitHub Releases and their Ed25519 signatures are verified
  before installation. No document data is sent. Portable builds and the
  published 1.0.16 Windows release open the GitHub Releases page for manual
  updates instead.
- On Linux, the AppImage contacts the GitHub Releases API only when the user
  selects **Check for Updates…**. If the user accepts an available update, it
  downloads the AppImage and its published SHA-256 checksum from GitHub.
- The optional Linux installer downloads the AppImage and checksum from GitHub
  when the user runs the installer.
- Project, privacy, license and support links open in the user's browser only
  when selected.

No PDF, PDF content or filename is included intentionally in these update
requests. GitHub may receive normal connection information such as an IP
address and user agent under the
[GitHub Privacy Statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement).
