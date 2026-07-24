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
APP_VERSION="1.0.4" \
.build-venv/bin/python build_macos.py
```

The build script signs bundled Mach-O files first, seals the application with
hardened runtime and a secure timestamp, creates the DMG, and signs the DMG.
It also writes a third-party license directory, a runtime dependency manifest,
and a corresponding-source notice into the application bundle. Set `SOURCE_REF`
to the Git tag that will identify the exact matching source:

```sh
SOURCE_REF="v1.0.4" \
MACOS_SIGNING_IDENTITY="Developer ID Application: NAME (TEAM_ID)" \
APP_VERSION="1.0.4" \
.build-venv/bin/python build_macos.py
```

## Notarize, staple, and verify

```sh
DMG="release/FS-PDF-Compressor-1.0.4-arm64.dmg"

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

## Secure in-app updates

Release 1.0.4 and later bundle Sparkle. It checks the public `appcast.xml`
feed once per day and also exposes **Check for Updates…** in the application
menu. Sparkle only accepts archives signed with the application's EdDSA update
key and the app itself remains protected by Developer ID signing.

The private EdDSA key stays in the macOS Keychain. Never export it, place it in
this repository, print it, or generate a replacement key without an explicit
key-rotation plan. The build script only looks up the existing public half from
Keychain and places it in the built app's `Info.plist`; it fails rather than
creating a new key if the Keychain item is missing.

Each release now produces a normal DMG and an update ZIP:

```sh
ZIP="release/FS-PDF-Compressor-1.0.4-arm64.zip"
```

After uploading both assets to the matching GitHub Release, generate the
signed update feed and commit the resulting `docs/appcast.xml`:

```sh
scripts/generate_appcast.sh 1.0.4
git add docs/appcast.xml
git commit -m "Publish 1.0.4 update feed"
git push
```

The script uses the private update key directly from the macOS login Keychain
and never writes it to disk. The first invocation may ask macOS for permission
to let `generate_appcast` use the key; approve that access without revealing or
exporting the key. Publish the appcast only after the ZIP release asset exists
at its GitHub URL.

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
