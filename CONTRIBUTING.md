# Contributing

Thanks for helping keep FS PDF Compressor fast and simple.

## Before opening a pull request

1. Open an issue for behavior changes or new interface options.
2. Keep the default workflow drag-and-drop first and visually minimal.
3. Do not add PDF uploads, analytics or telemetry. Keep network access limited
   to documented update mechanisms and links explicitly opened by the user.
4. Test changes on every platform they affect: Apple Silicon running macOS 14
   or later and/or x86_64 Linux.
5. Keep contributions compatible with AGPL-3.0-or-later.

## Development

### macOS

```shell
brew install python@3.12 ghostscript
python3.12 -m venv .build-venv
.build-venv/bin/python -m pip install -r requirements-build.txt
.build-venv/bin/python native_app.py
```

### Linux

```shell
sudo apt-get install ghostscript python3-venv
python3 -m venv .linux-build-venv
.linux-build-venv/bin/python -m pip install -r requirements-linux.txt
.linux-build-venv/bin/python linux_app.py
```

Before submitting:

```shell
.build-venv/bin/python -m py_compile \
  native_app.py build_macos.py linux_app.py build_linux.py \
  fs_pdf_compressor/*.py
.build-venv/bin/python build_macos.py
codesign --verify --deep --strict "release/FS PDF Compressor.app"
```

For Linux changes, also build the AppImage with the GitHub Actions workflow
and test compression with all three quality profiles on an x86_64 Linux
desktop.

By contributing, you agree that your contribution is licensed under the same
AGPL-3.0-or-later terms as the project.
