# Changelog

## 1.0.13 — 2026-09-04

- Reduced the app's idle memory footprint, especially on macOS, so FS PDF
  Compressor stays lighter while waiting for files without changing its
  compression workflow or quality profiles.
- Keep Sparkle's signed update installation intact, but defer loading its
  full framework until an update may be available or the user chooses
  **Check for Updates…**. A small HTTPS metadata check avoids paying that
  memory cost during ordinary use.
- Bound Ghostscript diagnostic output and avoid temporary duplicate path
  collections during batch setup, reducing unnecessary memory retained by
  unusually noisy failures or large selections.
- Limit result-table redraw work to changed or visible rows on macOS, and
  release the completed Qt worker and thread on Linux.
- Add a Windows 11 x64 distribution: a per-user installer and portable ZIP,
  both published with SHA-256 checksums and the required Ghostscript AGPL
  notices and corresponding-source offer.
- Add Windows Explorer's **Compress with FS PDF Compressor** action, a
  single-instance desktop Drop Zone, compression-result reductions, and
  Recycle Bin preservation of an original PDF that is safely replaced.

## 1.0.12 — 2026-09-02

- Add **Compress with FS PDF Compressor** to Finder's **Quick Actions** menu
  for one or multiple selected PDF files on macOS.
- Pass multiple PDF paths from Linux desktop entries to the application.
- Add per-user file-manager actions for GNOME Files (Nautilus) and KDE Dolphin
  when installing the Linux AppImage.

## 1.0.11 — 2026-08-12

- Preserve masked artwork inside mixed RGB/CMYK transparency groups by keeping
  the source color spaces when Ghostscript applies the Balanced or Maximum
  compression profile.

## 1.0.10 — 2026-08-12

- Preserve PDF optional content and marked content during compression so
  artwork intended for on-screen viewing is not dropped as print-only output.
- Generate PDF 1.7 output and explicitly retain the document's screen
  appearance while keeping all three Ghostscript compression profiles.
- Add a regression test for PDFs whose visible artwork is hidden when printed.
- Publish matching macOS, AppImage and Snap Store builds, including a
  Developer ID-signed and Apple-notarized DMG and the signed Sparkle update.

## 1.0.9 — 2026-08-05

- Fixed AppImage startup on minimal X11 systems by bundling the complete Qt
  XCB runtime dependency closure.
- Rebuilt the matching macOS release with Developer ID signing, notarization
  and stapling.

## 1.0.8 — 2026-08-05

- Bundled and verified the Qt X11 runtime libraries required by the Linux
  AppImage.
- Improved public search metadata and release documentation.

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
