# SPDX-License-Identifier: AGPL-3.0-or-later
"""Critical regressions: originals must survive every unsuccessful operation."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from fs_pdf_compressor import core
from fs_pdf_compressor.file_guard import document_lock
from fs_pdf_compressor.system_trash import TrashError


class FileSafetyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.original = self.root / "report.pdf"
        self.payload = b"original document " * 100
        self.original.write_bytes(self.payload)
        self.output = b"%PDF-1.7\n%%EOF"
        self.config = mock.patch.object(core, "get_ghostscript_config", return_value=("gs", {}))
        self.config.start()
        self.addCleanup(self.config.stop)

    def run_compression(self, keep=False, after_write=None):
        def run(command, **kwargs):
            path = next(arg.removeprefix("-sOutputFile=") for arg in command if arg.startswith("-sOutputFile="))
            Path(path).write_bytes(self.output)
            if after_write:
                after_write()
            return subprocess.CompletedProcess(command, 0)
        with mock.patch.object(core.subprocess, "run", side_effect=run):
            return core.compress_pdf(str(self.original), "/ebook", keep)

    def test_existing_legacy_temporary_is_never_overwritten(self):
        legacy = Path(str(self.original) + ".temp.pdf")
        legacy.write_bytes(b"unrelated user data")
        with mock.patch.object(core, "move_to_system_trash") as trash:
            _, metrics = self.run_compression(keep=True)
        trash.assert_not_called()
        self.assertIsNotNone(metrics)
        self.assertEqual(legacy.read_bytes(), b"unrelated user data")
        self.assertEqual(self.original.read_bytes(), self.payload)
        self.assertEqual((self.root / "report compressed.pdf").read_bytes(), self.output)

    def test_empty_and_truncated_outputs_never_replace_original(self):
        for output in (b"", b"%PDF-1.7\ntruncated", b"not a PDF\n%%EOF"):
            with self.subTest(output=output), mock.patch.object(core, "move_to_system_trash") as trash:
                self.output = output
                _, metrics = self.run_compression()
                self.assertIsNone(metrics)
                self.assertEqual(self.original.read_bytes(), self.payload)
                self.assertEqual(list(self.root.iterdir()), [self.original])
                trash.assert_not_called()

    def test_external_edit_prevents_replacement(self):
        with mock.patch.object(core, "move_to_system_trash") as trash:
            _, metrics = self.run_compression(after_write=lambda: self.original.write_bytes(b"edited elsewhere"))
        trash.assert_not_called()
        self.assertIsNone(metrics)
        self.assertEqual(self.original.read_bytes(), b"edited elsewhere")

    def test_trash_failure_replaces_and_creates_no_copy(self):
        with mock.patch.object(core, "move_to_system_trash", side_effect=TrashError("unavailable")):
            status, metrics = self.run_compression()
        self.assertNotIn("not replaced", status)
        self.assertIsNotNone(metrics)
        self.assertEqual(self.original.read_bytes(), self.output)
        self.assertEqual(list(self.root.iterdir()), [self.original])

    def test_trash_moves_then_fails_still_installs_compressed_output(self):
        def fail(path):
            path.unlink()  # Simulate a backend that moved/deleted before failing.
            raise TrashError("incomplete trash operation")
        with mock.patch.object(core, "move_to_system_trash", side_effect=fail):
            _, metrics = self.run_compression()
        self.assertIsNotNone(metrics)
        self.assertEqual(self.original.read_bytes(), self.output)
        self.assertEqual(list(self.root.iterdir()), [self.original])

    def test_trash_and_install_failure_restore_original(self):
        replace = os.replace
        def fail_trash(path):
            path.unlink()
            raise TrashError("moved before failure")
        def fail_install(source, destination):
            if not Path(source).name.startswith(".fs-pdf-recovery-"):
                raise OSError("install failed")
            return replace(source, destination)
        with mock.patch.object(core, "move_to_system_trash", side_effect=fail_trash), mock.patch.object(core.os, "replace", side_effect=fail_install):
            _, metrics = self.run_compression()
        self.assertIsNone(metrics)
        self.assertEqual(self.original.read_bytes(), self.payload)
        self.assertEqual(list(self.root.iterdir()), [self.original])

    def test_successful_replacement_recycles_exact_original_name_and_bytes(self):
        recycled = {}
        def recycle(path):
            recycled[path.name] = path.read_bytes()
            path.unlink()
        with mock.patch.object(core, "move_to_system_trash", side_effect=recycle):
            _, metrics = self.run_compression()
        self.assertEqual(recycled, {"report.pdf": self.payload})
        self.assertEqual(self.original.read_bytes(), self.output)
        self.assertIsNotNone(metrics)
        self.assertEqual(list(self.root.iterdir()), [self.original])

    def test_failed_install_after_recycling_restores_original(self):
        replace = os.replace
        def fail_install(source, destination):
            if Path(source).name.startswith(".fs-pdf-") and not Path(source).name.startswith(".fs-pdf-recovery-"):
                raise OSError("could not install compressed PDF")
            return replace(source, destination)
        with mock.patch.object(core, "move_to_system_trash", side_effect=lambda path: path.unlink()), mock.patch.object(core.os, "replace", side_effect=fail_install):
            _, metrics = self.run_compression()
        self.assertIsNone(metrics)
        self.assertEqual(self.original.read_bytes(), self.payload)

    @unittest.skipIf(os.name == "nt", "Windows mutex is reentrant within the same thread")
    def test_second_compression_of_locked_document_is_rejected(self):
        with document_lock(str(self.original)):
            status, metrics = self.run_compression()
        self.assertIn("already being compressed", status)
        self.assertIsNone(metrics)
        self.assertEqual(self.original.read_bytes(), self.payload)


if __name__ == "__main__":
    unittest.main()
