# Snap packaging

This directory contains the strictly confined Snap package for FS PDF
Compressor. It packages the Linux Qt interface, Ghostscript and the required
runtime libraries without network access.

## Build and test

On Ubuntu 24.04 with Snapcraft installed:

```sh
snapcraft pack
sudo snap install --dangerous ./fs-pdf-compressor_1.0.10_amd64.snap
fs-pdf-compressor
```

Test opening a PDF from the file picker, drag and drop, all three compression
profiles, keeping the original, and a PDF on removable media after connecting
the `removable-media` interface if needed.

The Snap Store handles updates. The AppImage-specific `Check for Updates…`
menu item is intentionally unavailable when the application runs as a Snap.

## Publish

Upload a tested build to `candidate`, install that store revision on a separate
Linux system, and promote the verified revision to `stable`:

```sh
snapcraft upload ./fs-pdf-compressor_1.0.10_amd64.snap --release candidate
snapcraft status fs-pdf-compressor
snapcraft release fs-pdf-compressor REVISION stable
```
