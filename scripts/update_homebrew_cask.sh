#!/bin/zsh

set -euo pipefail

VERSION="${1:-}"
DMG_PATH="${2:-}"
CASK_FILE="packaging/homebrew/fs-pdf-compressor.rb"

if [[ -z "$VERSION" ]]; then
  print -u2 "usage: scripts/update_homebrew_cask.sh VERSION [DMG_PATH]"
  exit 64
fi

if [[ -z "$DMG_PATH" ]]; then
  DMG_PATH="release-${VERSION}-final/FS-PDF-Compressor-${VERSION}-arm64.dmg"
fi

if [[ ! -f "$DMG_PATH" ]]; then
  print -u2 "DMG not found: $DMG_PATH"
  exit 1
fi

if [[ ! -f "$CASK_FILE" ]]; then
  print -u2 "Cask source not found: $CASK_FILE"
  exit 1
fi

SHA256="$(shasum -a 256 "$DMG_PATH" | awk '{print $1}')"
ASSET_URL="https://github.com/gitlares/fs-pdf-compressor/releases/download/v${VERSION}/FS-PDF-Compressor-${VERSION}-arm64.dmg"

print "Checking release asset: $ASSET_URL"
curl --fail --silent --show-error --location --head "$ASSET_URL" >/dev/null

VERSION="$VERSION" SHA256="$SHA256" perl -0pi -e \
  's/version "[^"]+"/version "$ENV{VERSION}"/; s/sha256 "[^"]+"/sha256 "$ENV{SHA256}"/' \
  "$CASK_FILE"

print "Updated $CASK_FILE"
print "Version: $VERSION"
print "SHA-256: $SHA256"
print "Next: run brew audit --cask --new fs-pdf-compressor from a Homebrew/homebrew-cask checkout, then submit the Cask there."
