#!/usr/bin/env bash
set -euo pipefail

version=10.07.1
checksum=1cdb766de8db8f1e589c817f09c5855ea5f65dfc8540e465a69ac14c18416025
source_url="https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10071/ghostscript-${version}.tar.xz"
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
