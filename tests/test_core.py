# SPDX-License-Identifier: AGPL-3.0-or-later

import tempfile
import unittest
from pathlib import Path

from fs_pdf_compressor.core import compressed_copy_path, expand_pdf_paths


class PdfPathTests(unittest.TestCase):
    def test_expand_paths_accepts_files_and_folders_without_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.pdf"
            second = root / "nested" / "second.PDF"
            ignored = root / "notes.txt"
            second.parent.mkdir()
            first.touch()
            second.touch()
            ignored.touch()

            paths = expand_pdf_paths([str(first), str(root)])

            self.assertEqual(paths, [str(first), str(second)])

    def test_compressed_copy_path_never_overwrites_an_existing_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "report.pdf"
            original.touch()
            (root / "report compressed.pdf").touch()

            destination = compressed_copy_path(str(original))

            self.assertEqual(destination, str(root / "report compressed 2.pdf"))


if __name__ == "__main__":
    unittest.main()
