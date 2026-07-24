# Changelog

## 1.0.3 — Unreleased

- Replaced the plain-text completion output with a compact, native-style results
  table that keeps filenames and reductions aligned.
- Added a visible quality-profile selector: Preserve quality, Balanced, and
  Maximum compression. Balanced remains the default.
- Added completion totals for the average reduction and total space saved.
- Added a local-only diagnostic log and a clear error state when a compression
  worker cannot start or Ghostscript returns an error.
- Added bundled Python runtime notices, an exact dependency manifest, and a
  corresponding-source notice for distribution compliance.

## 1.0.2 — 2026-07-23

- Prepared a Developer ID-signed, Apple-notarized Apple Silicon distribution
  artifact. It was superseded before public publication by 1.0.3.

## 1.0.1 — 2026-07-22

- Added an optional PayPal support link to the application menu and About panel.
- Added GitHub funding metadata and project support documentation.
- Standardized all public application interface text in English.

## 1.0.0 — 2026-07-22

First public release.

- Native AppKit drag-and-drop interface for macOS.
- Balanced, quality-preserving and maximum-compression profiles.
- Optional preservation of the original PDF.
- Recompression of the previous batch.
- Embedded Ghostscript 10.07.1 and runtime dependencies.
- Local-only processing with no telemetry or uploads.
