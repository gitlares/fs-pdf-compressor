# SPDX-License-Identifier: AGPL-3.0-or-later

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_windows


class WindowsBuildTests(unittest.TestCase):
    def test_windows_package_uses_the_product_icon_and_drop_zone_assets(self):
        source = Path(build_windows.__file__).read_text(encoding="utf-8")

        self.assertIn('"--icon",', source)
        self.assertIn('PDFCompresor.ico', source)
        self.assertIn('PDFCompresor.png', source)
        self.assertTrue((Path(build_windows.__file__).parent / "assets" / "PDFCompresor.ico").is_file())

    def test_windows_installer_registers_explorer_action_and_product_icon(self):
        installer = (
            Path(build_windows.__file__).parent / "installer" / "windows.iss"
        ).read_text(encoding="utf-8")

        self.assertIn("SetupIconFile", installer)
        self.assertIn("IconFilename", installer)
        self.assertIn("Compress with FS PDF Compressor", installer)
        self.assertIn("MultiSelectModel", installer)
        self.assertIn("Player", installer)

    def test_ghostscript_root_prefers_explicit_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "gs10.07.1"
            binary = root / "bin" / "gswin64c.exe"
            binary.parent.mkdir(parents=True)
            binary.touch()

            with patch.dict(os.environ, {"GHOSTSCRIPT_ROOT": str(root)}, clear=False):
                self.assertEqual(build_windows.ghostscript_root(), root)

    def test_bundle_compliance_documents_records_unmodified_ghostscript(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_license = root / "LICENSE"
            source_notices = root / "THIRD_PARTY_NOTICES.md"
            source_license.write_text("AGPL")
            source_notices.write_text("notices")

            with patch.object(build_windows, "ROOT", root):
                with patch("build_windows.package_version", side_effect=lambda name: f"{name}-version"):
                    build_windows.bundle_compliance_documents(root / "resources", "10.07.1")

            manifest = (root / "resources" / "THIRD_PARTY_MANIFEST.json").read_text()
            self.assertIn('"ghostscript_modified": false', manifest)
            offer = (root / "resources" / "SOURCE_OFFER.md").read_text()
            self.assertIn("ghostpdl-10.07.1.tar.xz", offer)


if __name__ == "__main__":
    unittest.main()
