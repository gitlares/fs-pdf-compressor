# Privacy

FS PDF Compressor processes PDF files entirely on the user's Mac.

- No files or file contents are uploaded.
- No account is required.
- No analytics, telemetry or crash-reporting service is included.
- No usage history is collected.
- Network access occurs only when the user explicitly opens a project or license
  link from the application menu.

If compression fails, the app records the technical error locally at
`~/Library/Logs/FS PDF Compressor/compression.log`. This local diagnostic file
is never uploaded or shared automatically.

The application invokes the bundled Ghostscript executable locally and writes
the compressed PDF to the selected file location.
