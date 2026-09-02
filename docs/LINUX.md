# Linux

The Linux edition is developed in the same repository as the macOS app. It
shares the PDF-processing engine and quality profiles, while using a Qt desktop
interface that deliberately mirrors the FS PDF Compressor layout.

The first distribution target is an x86_64 AppImage. It includes Ghostscript,
so users do not need Homebrew, a package manager, or a separate Ghostscript
installation.

## Drop Zone

Drop Zone is an optional small target for compressing PDFs without reopening
the main window. Enable it from **Application → Show Drop Zone** and disable it
by unchecking the same menu item. You can move it, double-click it to reopen
the main window, and the app remembers its enabled state and position.

On X11, the window manager can keep Drop Zone at desktop level. On Wayland,
applications cannot reliably choose their own desktop layer or absolute
placement because those decisions belong to the compositor. Drop Zone may
therefore appear as a normal floating utility instead. Better Wayland
integration is being investigated.

## Install the release

Download and run the AppImage directly:

```sh
curl -fLO https://github.com/gitlares/fs-pdf-compressor/releases/latest/download/FS-PDF-Compressor-x86_64.AppImage
chmod +x FS-PDF-Compressor-x86_64.AppImage
./FS-PDF-Compressor-x86_64.AppImage
```

For applications-menu integration and a `fs-pdf-compressor` command, use the
per-user installer:

```sh
curl -fsSLO https://raw.githubusercontent.com/gitlares/fs-pdf-compressor/main/scripts/install_linux_appimage.sh
sh install_linux_appimage.sh
```

The installer does not use `sudo`. It verifies the AppImage against the
release's published SHA-256 file, installs it under
`~/.local/opt/fs-pdf-compressor`, and creates the desktop entry and command
inside `~/.local`. It also adds **Compress with FS PDF Compressor** to GNOME
Files' **Scripts** submenu and KDE Dolphin's **Actions** submenu for PDF files.
Both actions accept one or multiple selected PDFs. Other compatible file
managers can send one or multiple PDFs through **Open With**.

## Run during development

On an x86_64 Linux system with Python 3.12 or newer and Ghostscript:

```sh
sudo apt-get install ghostscript python3-venv
python3 -m venv .linux-build-venv
.linux-build-venv/bin/python -m pip install -r requirements-linux.txt
.linux-build-venv/bin/python linux_app.py
```

## Build an AppImage

The GitHub Actions workflow **Build Linux AppImage** is the preferred
way to build it. It runs on Ubuntu 22.04 so the output has a conservative
runtime baseline. Start it manually from the Actions tab, download its
artifact, then on Linux run:

```sh
chmod +x FS-PDF-Compressor-x86_64.AppImage
./FS-PDF-Compressor-x86_64.AppImage
```

For a local Linux build, install Ghostscript and provide a verified
`appimagetool` executable:

```sh
APPIMAGETOOL=/absolute/path/to/appimagetool \
  .linux-build-venv/bin/python build_linux.py
```

The release AppImage is tested with all three quality profiles. It is x86_64
only; ARM Linux is not supported yet.

## Updates

Released AppImages include both the standard AppImage `zsync` update metadata
and an **Application → Check for Updates…** action. The action downloads the
latest AppImage from the public GitHub Release, checks it against the published
SHA-256 file, then replaces and restarts the AppImage only after the running
copy exits. It needs write permission to the folder containing the AppImage.

Every Linux release must publish these three assets with these exact, stable
names, so installed copies can discover the newest release:

```text
FS-PDF-Compressor-x86_64.AppImage
FS-PDF-Compressor-x86_64.AppImage.sha256
FS-PDF-Compressor-x86_64.AppImage.zsync
```

`appimagetool` generates the `zsync` sidecar during the build for external
AppImage update clients.
