# Windows release testing

This checklist is for a candidate produced before a shared public release. For
the reproducible open-source build instructions, see [Windows builds](WINDOWS.md).

## Build prerequisites

Use a Windows 11 x64 virtual machine, or Windows 11 ARM with an **x64 Python**
installation running under Windows emulation. Install:

- Python 3.12 x64
- the official x64 AGPL Ghostscript runtime
- Inno Setup 6 (free installer compiler)

Ghostscript must be installed under `C:\Program Files\gs\gs<version>` or its
directory may be supplied with `GHOSTSCRIPT_ROOT`.

```powershell
py -3.12 -m venv .windows-build-venv
.windows-build-venv\Scripts\python -m pip install --upgrade pip
.windows-build-venv\Scripts\python -m pip install -r requirements-windows.txt
.windows-build-venv\Scripts\python build_windows.py
```

The unsigned installer, portable ZIP and SHA-256 files are written to
`release-windows/`. They contain the unmodified Ghostscript runtime, AGPL text,
a source offer, and an exact third-party manifest. The build script never signs,
uploads, releases, or changes `main`.

## UTM checklist

Install the setup executable from `release-windows/`, then test the installed
application. The portable ZIP is retained for troubleshooting if the
installer itself has a problem:

1. Run the installer and confirm the expected unsigned-publisher warning.
2. Drag in one PDF, several PDFs, and a folder of PDFs.
3. Test Preserve, Balanced, and Maximum compression.
4. With **Keep original** off, confirm the compressed PDF retains the original
   filename and the previous PDF appears in the Windows Recycle Bin.
5. Restore the previous PDF from the Recycle Bin to confirm it is recoverable.
6. Launch the installed shortcut twice and confirm the existing window is
   brought forward instead of opening another application instance.
7. Close the main window, confirm the desktop drop zone stays available, and
   double-click it to reopen the app.
8. With **Keep original** on, confirm the original remains beside
   `name compressed.pdf`.
9. Repeat a batch with **Again**.

Record the Windows edition, architecture, Ghostscript version, and any
SmartScreen message with the test result. Do not publish either package until
the checklist succeeds.

## WinSparkle update checklist

For the first installer release with WinSparkle, use two successive candidate
versions and a test feed signed with the embedded verification key:

1. Confirm `_internal/WinSparkle.dll` and its license texts are packaged.
2. Confirm the first-run automatic-check choice persists after restarting.
3. Run **Check for Updates…** against a feed with no newer release.
4. Offer a newer signed installer and verify download, installation in the
   existing directory, shutdown, and relaunch without duplicate instances.
5. Confirm Keep original, Drop Zone, and Explorer integration survive upgrading.
6. Change the downloaded installer bytes and verify installation is rejected.
7. Attempt installation while discovering a folder or compressing a batch;
   verify the current work is preserved and installation is refused until idle.
8. Once installation starts, verify new drops and **Again** cannot start work.
9. Unpack the portable ZIP in another directory and confirm it uses the manual
   release-page link and never runs the installed application's updater.

See [signed Windows updates](RELEASING.md#windows-signed-updates) for feed
generation. The Ed25519 update signature does not replace Authenticode; the
Windows installer remains unsigned unless separately code-signed.

## Automated validation recorded on 2026-10-08

[GitHub Actions run 37840732060](https://github.com/gitlares/fs-pdf-compressor/actions/runs/37840732060)
passed for source commit `851db786106137e7a1424ca00553750114611813` on
Windows Server 2022. It built the Windows 1.0.16.1 installer and portable ZIP,
verified package contents, used the real WinSparkle DLL to authenticate a
download and reject a tampered payload, checked an empty update feed, upgraded
the published 1.0.16 installer using the native-verified payload, verified
preserved preferences and Explorer registration, and checked installed
application startup. See the [permanent result](validation/windows-1.0.16.1-ci.json).

The native download test used a disposable signing key and a loopback feed.
It did not use the production signing key or publish an update. Unattended
installation and process startup do not replace visual review of the update
approval dialog, relaunch, actual Explorer action, drag/drop, or Windows 11
desktop behavior. Those checks remain pending before a public release.
