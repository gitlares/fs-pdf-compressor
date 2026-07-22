# Contributing

Thanks for helping keep FS PDF Compressor fast and simple.

## Before opening a pull request

1. Open an issue for behavior changes or new interface options.
2. Keep the default workflow drag-and-drop first and visually minimal.
3. Do not add network requests, analytics, telemetry or PDF uploads.
4. Test on an Apple Silicon Mac running macOS 13 or later.
5. Keep contributions compatible with AGPL-3.0-or-later.

## Development

```shell
brew install python@3.12 ghostscript
python3.12 -m venv .build-venv
.build-venv/bin/python -m pip install -r requirements-build.txt
.build-venv/bin/python native_app.py
```

Before submitting:

```shell
.build-venv/bin/python -m py_compile native_app.py build_macos.py
.build-venv/bin/python build_macos.py
codesign --verify --deep --strict "release/FS PDF Compressor.app"
```

By contributing, you agree that your contribution is licensed under the same
AGPL-3.0-or-later terms as the project.
