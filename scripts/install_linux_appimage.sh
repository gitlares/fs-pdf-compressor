#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

set -eu

APPIMAGE_NAME="FS-PDF-Compressor-x86_64.AppImage"
RELEASE_BASE="https://github.com/gitlares/fs-pdf-compressor/releases/latest/download"
INSTALL_DIR="${HOME}/.local/opt/fs-pdf-compressor"
BIN_DIR="${HOME}/.local/bin"
APPLICATIONS_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/256x256/apps"

if [ "$(uname -s)" != "Linux" ] || [ "$(uname -m)" != "x86_64" ]; then
  echo "FS PDF Compressor currently supports x86_64 Linux only." >&2
  exit 1
fi

for command_name in curl sha256sum mktemp install; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Required command not found: $command_name" >&2
    exit 1
  fi
done

temporary_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$temporary_dir"
}
trap cleanup EXIT HUP INT TERM

appimage_path="${temporary_dir}/${APPIMAGE_NAME}"
checksum_path="${appimage_path}.sha256"

echo "Downloading FS PDF Compressor…"
curl --fail --location --proto '=https' --tlsv1.2 \
  --output "$appimage_path" "${RELEASE_BASE}/${APPIMAGE_NAME}"
curl --fail --location --proto '=https' --tlsv1.2 \
  --output "$checksum_path" "${RELEASE_BASE}/${APPIMAGE_NAME}.sha256"

echo "Verifying SHA-256 checksum…"
(
  cd "$temporary_dir"
  sha256sum --check "${APPIMAGE_NAME}.sha256"
)

install -d "$INSTALL_DIR" "$BIN_DIR" "$APPLICATIONS_DIR" "$ICON_DIR"
install -m 755 "$appimage_path" "${INSTALL_DIR}/${APPIMAGE_NAME}"
ln -sfn "${INSTALL_DIR}/${APPIMAGE_NAME}" "${BIN_DIR}/fs-pdf-compressor"

(
  cd "$temporary_dir"
  chmod 755 "$appimage_path"
  "$appimage_path" --appimage-extract fs-pdf-compressor.png >/dev/null 2>&1 || true
)
if [ -f "${temporary_dir}/squashfs-root/fs-pdf-compressor.png" ]; then
  install -m 644 \
    "${temporary_dir}/squashfs-root/fs-pdf-compressor.png" \
    "${ICON_DIR}/fs-pdf-compressor.png"
fi

desktop_file="${temporary_dir}/fs-pdf-compressor.desktop"
cat >"$desktop_file" <<EOF
[Desktop Entry]
Type=Application
Name=FS PDF Compressor
Comment=Fast and Simple PDF compression
Exec="${INSTALL_DIR}/${APPIMAGE_NAME}" %F
Icon=fs-pdf-compressor
Categories=Office;Utility;
MimeType=application/pdf;
Terminal=false
EOF
install -m 644 "$desktop_file" "${APPLICATIONS_DIR}/fs-pdf-compressor.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi

echo
echo "Installed FS PDF Compressor."
echo "Open it from your applications menu or run: fs-pdf-compressor"
