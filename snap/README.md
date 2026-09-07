# Snap packaging

This directory contains the strictly confined Snap package for FS PDF
Compressor. It packages the Linux Qt interface, Ghostscript and the required
runtime libraries without network access.

## Build and test

On Ubuntu 24.04 with Snapcraft installed:

```sh
snapcraft pack
sudo snap install --dangerous ./fs-pdf-compressor_1.0.14_amd64.snap
fs-pdf-compressor
```

Test opening a PDF from the file picker, drag and drop, all three compression
profiles, keeping the original, and a PDF on removable media after connecting
the `removable-media` interface if needed.

The Snap Store handles updates. `Check for Updates…` explains this in the
Snap build. Replacing a PDF uses the host desktop Trash portal; if unavailable,
the app still replaces it with the smaller validated output and logs that
trash recovery was unavailable. Keep original remains a separate copy mode.

### Runtime resources

The layouts in `snapcraft.yaml` expose the bundled Ghostscript resources,
fonts, and ICC profiles at Ghostscript's compiled-in `/usr/share` paths inside
the Snap namespace. Do not remove them: a confined build otherwise fails with
`Can't find initialization file gs_init.ps`, even when the same code works in
an AppImage. The Wayland cursor/EGL runtime libraries are also staged explicitly.

### Magnolia isolated-build workaround

On Magnolia, LXD's requested working directory was not honored during the
managed build: the command started in `/` instead of `/root/project`. The
build succeeded by explicitly changing directory in a shell **inside the
existing, isolated Snapcraft container**, with the checkout mounted there.
The commands executed in that container were:

```sh
mkdir -p /tmp/craft-state
cd /root/project
CRAFT_MANAGED_MODE=1 snapcraft pack --destructive-mode
```

Do not run this destructive-mode command on the host. `/tmp/craft-state` is
required for Snapcraft to record the managed build result. Stop the test
container and detach its project mount after testing. No LXD group permission
changes or Snap Store uploads are needed for this local workflow.

The opt-in `scripts/verify_snap_confined.sh` runs all profiles and both output
modes using the installed Snap's modules. `scripts/verify_linux_appimage.py
--snap` launches the installed application under Xvfb and checks its output,
including an unavailable portal. These tests use generated PDFs only; they
do not certify a manual Wayland session or successful host-trash recovery.

## Publish

Upload a tested build to `candidate`, install that store revision on a separate
Linux system, and promote the verified revision to `stable`:

```sh
snapcraft upload ./fs-pdf-compressor_1.0.14_amd64.snap --release candidate
snapcraft status fs-pdf-compressor
snapcraft release fs-pdf-compressor REVISION stable
```
