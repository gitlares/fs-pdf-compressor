# Flatpak and Flathub assessment

FS PDF Compressor is a good distribution candidate for Flatpak because it is
a graphical, local-first desktop application. A Flathub package would be a
separate Linux distribution channel; it would not replace the AppImage.

## Proposed identity

- Application ID: `io.github.gitlares.FSPDFCompressor`
- Runtime family: current `org.kde.Platform` and `org.kde.Sdk`
- Target architectures: `x86_64` and `aarch64` only after both have been
  built and tested

The application ID is tied to the `gitlares` GitHub project identity and must
be used consistently by the manifest, desktop file, icon, and MetaInfo file.

## What must change before a submission

This is deliberately not a Flatpak manifest yet. A manifest that simply
wraps the AppImage or downloads wheels would be rejected by Flathub.

1. **Build the Python runtime dependencies from source.** The KDE 6.9 runtime
   available during the assessment does not provide either `PySide6` or
   Ghostscript. The final manifest must build compatible PySide6 bindings and
   Ghostscript from publicly declared source archives, with checksums. It may
   not install prebuilt PyPI wheels or download dependencies during the build.
2. **Validate file access through portals.** FS PDF Compressor intentionally
   replaces an original only when the compressed PDF is smaller. The Flatpak
   build must prove that choosing a file, choosing a folder, and dropping PDFs
   grant the app the required read and write access through the document
   portal, without a broad `--filesystem=home` or `--filesystem=host`
   permission.
3. **Make store updates the only Flatpak update path.** The AppImage updater
   must be disabled when `FLATPAK_ID` is set; Flatpak updates are handled by
   the user's Flatpak installation, not by replacing the running package.
4. **Add desktop integration metadata.** The package needs a desktop file,
   256px-or-larger icon, and a valid AppStream MetaInfo file with an English
   description, screenshots, project URL, and AGPL-3.0-or-later license.
5. **Build and lint on Linux.** The submission must pass `flatpak-builder`
   and `flatpak-builder-lint`, then launch successfully on a Linux desktop
   and compress a representative PDF with Preserve, Balanced, and Maximum.

## Permissions target

The initial proposal should request only what the Qt interface needs:

- Wayland and fallback X11 sockets
- IPC sharing for Qt
- Document portal access initiated by the user

Network access is not required for PDF compression and should not be granted.
The optional Drop Zone must remain functional under the compositor's normal
window-placement rules; Flatpak cannot bypass Wayland's desktop-layer
restrictions.

## Submission boundary

Flathub requires all dependencies to be declared as source and reviews
permissions, metadata, and build reproducibility. Its current policy also
requires that the Flathub submission pull request itself be created manually
by the project maintainer. This repository can contain human-reviewed
packaging work, but the final submission must be opened manually from the
Flathub web workflow.

## Review checklist

- [ ] Decide whether to fund the source build and maintenance of PySide6.
- [ ] Add the portal-access integration test before requesting permissions.
- [ ] Implement the Flatpak-only updater behavior.
- [ ] Provide AppStream screenshots and a final application description.
- [ ] Build, lint, and test both supported architectures.
- [ ] Open the final Flathub submission manually after human review.
