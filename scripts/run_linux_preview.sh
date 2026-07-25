#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec "$ROOT/.linux-build-venv/bin/python" "$ROOT/linux_app.py" "$@"
