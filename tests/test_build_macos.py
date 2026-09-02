# SPDX-License-Identifier: AGPL-3.0-or-later

import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_macos


class MacOSInfoPlistTests(unittest.TestCase):
    def test_write_info_plist_does_not_register_as_a_pdf_handler(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / "FS PDF Compressor.app"
            info_plist = app / "Contents" / "Info.plist"
            info_plist.parent.mkdir(parents=True)
            with info_plist.open("wb") as file:
                plistlib.dump({"CFBundleName": "FS PDF Compressor"}, file)

            with patch.object(build_macos, "APP", app):
                build_macos.write_info_plist(None)

            with info_plist.open("rb") as file:
                info = plistlib.load(file)

            self.assertNotIn("CFBundleDocumentTypes", info)
            self.assertNotIn("NSServices", info)
            self.assertEqual(
                info["CFBundleURLTypes"][0]["CFBundleURLSchemes"],
                ["fspdfcompressor"],
            )

    def test_bundle_quick_action_targets_pdf_files_in_finder(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / "FS PDF Compressor.app"
            quick_action = (
                app
                / "Contents"
                / "PlugIns"
                / "Compress with FS PDF Compressor.appex"
            )

            with (
                patch.object(build_macos, "APP", app),
                patch.object(build_macos, "QUICK_ACTION", quick_action),
                patch.object(build_macos, "run") as run,
                patch.object(build_macos, "sign") as sign,
            ):
                build_macos.bundle_quick_action()

            with (quick_action / "Contents" / "Info.plist").open("rb") as file:
                info = plistlib.load(file)

            extension = info["NSExtension"]
            attributes = extension["NSExtensionAttributes"]
            self.assertEqual(
                extension["NSExtensionPointIdentifier"], "com.apple.ui-services"
            )
            self.assertEqual(
                attributes["NSExtensionServiceFinderPreviewLabel"],
                "Compress with FS PDF Compressor",
            )
            self.assertIn("com.adobe.pdf", attributes["NSExtensionActivationRule"])
            self.assertIn("clang", run.call_args.args)
            sign.assert_called_once_with(
                quick_action,
                entitlements=build_macos.QUICK_ACTION_ENTITLEMENTS,
            )


if __name__ == "__main__":
    unittest.main()
