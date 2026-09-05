# Windows candidate testing

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

The unsigned, private installer, portable ZIP and SHA-256 files are written to
`release-windows/`. They contain the unmodified Ghostscript runtime, AGPL text,
a source offer, and an exact third-party manifest. The build script never signs,
uploads, releases, or changes `main`.

## UTM checklist

Install the private setup executable from `release-windows/`, then test the
installed application. The portable ZIP is retained only for diagnosis if the
installer itself has a problem:

1. Run the installer and accept Windows' unsigned-app warning only for this private VM.
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
SmartScreen message with the test result. Do not distribute the ZIP beyond
private testing until the checklist succeeds.
