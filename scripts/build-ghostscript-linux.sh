#!/usr/bin/env bash
set -euo pipefail

version=10.08.0
checksum=c20492bc8ebb96c87fa2e52a0926e1cda8cde95d66145e018ac713fed5da38cf
source_url="https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10080/ghostscript-${version}.tar.xz"
prefix="${1:?Pass the installation prefix}"
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

curl --fail --location --retry 3 --output "$work_dir/ghostscript.tar.xz" "$source_url"
printf '%s  %s\n' "$checksum" "$work_dir/ghostscript.tar.xz" | sha256sum --check --status
tar -xf "$work_dir/ghostscript.tar.xz" -C "$work_dir"
cd "$work_dir/ghostscript-${version}"
./configure --prefix="$prefix"
make -j "$(nproc)"
make install
test "$("$prefix/bin/gs" --version)" = "$version"
