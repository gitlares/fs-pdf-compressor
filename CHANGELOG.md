# Changelog

## 1.0.13 — 2026-09-04

- Reduced memory used while the application is open and waiting for files.
- Bound temporary Ghostscript diagnostics and avoid duplicate path collections
  during batch setup.
- Release completed Qt worker threads promptly and avoid unnecessary result
  table redraws, without changing compression behavior or quality profiles.

## 1.0.12 — 2026-09-02

- Accept one or multiple PDF paths from Linux file-manager actions.
- Keep PDF files associated with FS PDF Compressor without making it the
  default PDF viewer.

## 1.0.7 — 2026-07-26

- Added an optional **Drop Zone** for compressing PDFs without
  keeping the main window open. It is movable, remembers its position and
  remains idle without polling.
- Added native Drop Zone surfaces for AppKit and Qt. On macOS it is available
  in every Space. Linux uses the
  compositor's bottom-window hint and falls back to a normal floating utility
  when a Wayland compositor does not honor desktop-layer positioning.
- Added a native **Launch at Login** option on macOS for users who want Drop
  Zone ready after signing in.
- Split platform views, background workers, Drop Zone surfaces and batch
  summaries into focused modules without changing the shared Ghostscript
  compression behavior.
- Added initial unit tests for batch summaries, PDF path expansion and safe
  compressed-copy naming.
- Expanded the privacy statement for macOS and Linux, including local
  diagnostic-log locations and the exact network activity used for updates.
- Updated build, contribution and release documentation for both supported
  platforms.
- Improved AppImage portability by keeping the host system's glibc runtime.

## 1.0.6 — 2026-07-24

- Added a Linux desktop edition using PySide6, with the same local compression
  engine, quality profiles, batch results, and original-file safeguards as the
  native macOS app.
- Added a self-contained x86_64 AppImage that bundles Ghostscript, plus a
  GitHub Actions build workflow for reproducible Linux artifacts.
- Added AppImage update metadata (`zsync`) and a user-initiated **Application
  → Check for Updates…** flow that verifies the downloaded SHA-256 file before
  replacing and restarting the AppImage.
- Added a no-`sudo` Linux installer that verifies the release checksum and
  integrates the AppImage with the user's applications menu.
- Moved shared PDF compression behavior into a platform-neutral module so the
  macOS and Linux interfaces use the same processing rules.
- Refined the native macOS footer alignment and returned the three quality
  profiles to a compact options menu.

## 1.0.5 — 2026-07-23

- Expanded the public Apple Silicon distribution to **macOS 14 (Sonoma) and
  later**. Intel Macs remain unsupported.
- Added a macOS 14 GitHub Actions build pipeline that audits every bundled
  Mach-O file before a compatibility release is finalized locally.
- Preserved macOS links in the CI handoff archive and re-sign every embedded
  executable with Developer ID and a secure timestamp before notarization.
- Published a notarized, stapled DMG accepted by Gatekeeper, plus the signed
  Sparkle update archive and 1.0.5 update-feed entry.
- Updated the website, download fallback, README, and roadmap to reflect the
  1.0.5 release and macOS 14+ Apple Silicon support.

## 1.0.4 — 2026-07-23

- Added Sparkle-based in-app update checks, protected by a dedicated EdDSA
  update-signing key stored only in the macOS Keychain.
- Added **Check for Updates…** to the application menu.
- Added a signed update-feed workflow and a separately distributable update
  ZIP alongside the normal DMG.

## 1.0.3 — 2026-07-23

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
