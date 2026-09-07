#!/bin/sh
# Run ONLY through: snap run --shell fs-pdf-compressor -c 'sh /path/to/this/script /path/to/test/repository'
# Tests the installed Snap modules, not the checkout's application modules.
set -eu
: "${SNAP:?Run inside the installed Snap confinement}"
test_root="$1"
app_root="$SNAP/opt/fs-pdf-compressor"
cd "$SNAP_USER_DATA"
export PATH="$SNAP/usr/bin:$PATH"
export PYTHONPATH="$app_root/python:$app_root:$test_root"
export QT_QPA_PLATFORM=offscreen
exec "$SNAP/usr/bin/python3" -B -m scripts.verify_platform_safety --qt --allow-unavailable-trash
