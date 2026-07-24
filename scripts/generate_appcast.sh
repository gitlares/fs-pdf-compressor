#!/bin/zsh
# Generate a signed Sparkle appcast after the matching GitHub Release is live.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  print -u2 "Usage: scripts/generate_appcast.sh VERSION"
  exit 64
fi

VERSION="$1"
ROOT="${0:A:h:h}"
SPARKLE_VERSION="2.9.4"
SPARKLE_TOOL="$HOME/Library/Caches/FS PDF Compressor/Sparkle-${SPARKLE_VERSION}/bin/generate_appcast"
ARCHIVE="$ROOT/release-${VERSION}/FS-PDF-Compressor-${VERSION}-arm64.zip"
RELEASE_URL="https://github.com/gitlares/fs-pdf-compressor/releases/tag/v${VERSION}"
DOWNLOAD_PREFIX="https://github.com/gitlares/fs-pdf-compressor/releases/download/v${VERSION}/"

if [[ ! -x "$SPARKLE_TOOL" ]]; then
  print -u2 "Sparkle tools are missing. Run a signed build first."
  exit 1
fi
if [[ ! -f "$ARCHIVE" ]]; then
  print -u2 "Missing update ZIP: $ARCHIVE"
  exit 1
fi

WORK_DIR="$(mktemp -d /tmp/fs-pdf-appcast.XXXXXX)"
trap 'rm -rf "$WORK_DIR"' EXIT
cp "$ARCHIVE" "$WORK_DIR/"
cp "$ROOT/docs/appcast.xml" "$WORK_DIR/appcast.xml"

"$SPARKLE_TOOL" \
  --download-url-prefix "$DOWNLOAD_PREFIX" \
  --full-release-notes-url "$RELEASE_URL" \
  --link "https://gitlares.github.io/fs-pdf-compressor/" \
  --versions "$VERSION" \
  -o appcast.xml \
  "$WORK_DIR"

cp "$WORK_DIR/appcast.xml" "$ROOT/docs/appcast.xml"
print "Updated docs/appcast.xml for v${VERSION}."
