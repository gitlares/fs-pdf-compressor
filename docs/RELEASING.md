# Releasing FS PDF Compressor

This document intentionally contains no personal account details or secrets.
Keep machine-specific signing information in a local, Git-ignored operations
file.

## Prerequisites

- An active Apple Developer Program membership
- A valid `Developer ID Application` certificate and private key in Keychain
- An Apple app-specific password saved as a `notarytool` Keychain profile
- The project build virtual environment and Ghostscript dependencies

List available signing identities:

```sh
security find-identity -v -p codesigning
```

Save notarization credentials once (replace the placeholders and enter the
app-specific password securely when prompted):

```sh
xcrun notarytool store-credentials "FS-PDF-Compressor" \
  --apple-id "APPLE_ID" \
  --team-id "TEAM_ID"
```

## Build and sign

```sh
MACOS_SIGNING_IDENTITY="Developer ID Application: NAME (TEAM_ID)" \
APP_VERSION="1.0.3" \
.build-venv/bin/python build_macos.py
```

The build script signs bundled Mach-O files first, seals the application with
hardened runtime and a secure timestamp, creates the DMG, and signs the DMG.
It also writes a third-party license directory, a runtime dependency manifest,
and a corresponding-source notice into the application bundle. Set `SOURCE_REF`
to the Git tag that will identify the exact matching source:

```sh
SOURCE_REF="v1.0.3" \
MACOS_SIGNING_IDENTITY="Developer ID Application: NAME (TEAM_ID)" \
APP_VERSION="1.0.3" \
.build-venv/bin/python build_macos.py
```

## Notarize, staple, and verify

```sh
DMG="release/FS-PDF-Compressor-1.0.3-arm64.dmg"

xcrun notarytool submit "$DMG" \
  --keychain-profile "FS-PDF-Compressor" \
  --wait

xcrun stapler staple "$DMG"
xcrun stapler validate "$DMG"
spctl --assess --type open --context context:primary-signature \
  --verbose=4 "$DMG"
```

Publish only after the submission status is `Accepted`, stapling succeeds, and
Gatekeeper reports acceptance.

## Release compliance

Before publishing, create and push the Git tag named by `SOURCE_REF`. Attach
the DMG to the matching GitHub Release instead of committing the binary to Git.
The release source tag must be the source that produced the DMG. Verify these
files exist in the built application:

```sh
APP="release/FS PDF Compressor.app"
test -f "$APP/Contents/Resources/SOURCE_OFFER.md"
test -f "$APP/Contents/Resources/THIRD_PARTY_MANIFEST.json"
test -d "$APP/Contents/Resources/third-party-licenses/python-runtime"
```

## Compatibility audit

The current distribution is Apple Silicon only. A bundle's real minimum macOS
version is the highest deployment target among every included Mach-O binary,
not merely the value in `Info.plist`.

```sh
APP="release/FS PDF Compressor.app"
find "$APP/Contents" -type f -print0 | while IFS= read -r -d '' file; do
  if file -b "$file" | grep -q "Mach-O"; then
    minimum=$(xcrun vtool -show-build "$file" 2>/dev/null | \
      awk '/minos/{print $2; exit}')
    printf '%-7s %s\n' "${minimum:-unknown}" "$file"
  fi
done | sort -V
```

To support Intel Macs, produce and test a separate `x86_64` build or a true
universal bundle in which Python, PyObjC, Ghostscript, and all dependent
libraries contain both architectures.
