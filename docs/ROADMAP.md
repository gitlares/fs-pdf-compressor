# FS PDF Compressor roadmap

## Planned for 1.0.5 — maintainability and reliability

- Split the application controller into focused modules for AppKit views, batch
  state, and Ghostscript compression.
- Add a timeout and clearer recovery path for a Ghostscript process that does
  not finish.
- Move directory expansion off the main UI thread so large folders remain
  responsive.
- Add automated tests for output naming, size calculations, quality profiles,
  Ghostscript failures, and update-feed generation.
- Refactor the build script into named build, bundle, sign, and package phases.
- Require an explicit release output directory before deleting build artifacts.

These are engineering improvements. They must preserve the small native UI,
local-only processing, and the existing signed-update key.
