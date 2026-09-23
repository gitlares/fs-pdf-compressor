# SPDX-License-Identifier: AGPL-3.0-or-later
"""Qt lifecycle and platform-specific update behavior."""

import importlib.util
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(HAS_QT, "PySide6 environment required")
class QtLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6 import QtWidgets
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        import linux_app
        self.module = linux_app
        self.window = linux_app.PDFCompressorWindow()
        self.window.drop_zone.hide()
        self.addCleanup(self.window.drop_zone.deleteLater)
        self.addCleanup(self.window.deleteLater)

    def test_quit_waits_for_compression(self):
        self.window.processing = True
        with mock.patch.object(self.module.QtWidgets.QApplication, "quit") as quit_app, mock.patch.object(self.module.QtWidgets.QMessageBox, "information"):
            self.assertFalse(self.window.request_quit())
        quit_app.assert_not_called()

    def test_quit_waits_for_thread_shutdown(self):
        self.window.thread = object()
        with mock.patch.object(self.module.QtWidgets.QApplication, "quit") as quit_app, mock.patch.object(self.module.QtWidgets.QMessageBox, "information"):
            self.assertFalse(self.window.request_quit())
        quit_app.assert_not_called()
        self.window.thread = None

    def test_restart_waits_for_compression(self):
        self.window.pending_replacement = "/tmp/update.AppImage"
        self.window.processing = True
        with mock.patch.object(self.module, "replace_after_exit") as replace:
            self.window._restart_when_idle()
        replace.assert_not_called()

    def test_windows_update_opens_release_page(self):
        with mock.patch.object(self.module.sys, "platform", "win32"), mock.patch.object(self.module.QtGui.QDesktopServices, "openUrl") as open_url:
            self.window.check_for_updates()
        self.assertEqual(open_url.call_args.args[0].toString(), "https://github.com/gitlares/fs-pdf-compressor/releases/latest")

    def test_snap_update_explains_store_updates(self):
        with mock.patch.object(self.module.sys, "platform", "linux"), mock.patch.dict(os.environ, {"SNAP": "/snap/test"}), mock.patch.object(self.module.QtWidgets.QMessageBox, "information") as message:
            self.window.check_for_updates()
        self.assertIn("Snap Store", message.call_args.args[2])

    def test_keep_original_survives_reopening_and_can_be_turned_off(self):
        from PySide6 import QtCore

        original_settings = QtCore.QSettings
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "settings.ini")

            def isolated_settings(*_args):
                return original_settings(path, original_settings.IniFormat)

            with mock.patch.object(QtCore, "QSettings", side_effect=isolated_settings):
                first = self.module.PDFCompressorWindow()
                first.drop_zone.hide()
                self.addCleanup(first.drop_zone.deleteLater)
                self.addCleanup(first.deleteLater)
                self.assertFalse(first.keep_original.isChecked())

                first.keep_original.setChecked(True)
                second = self.module.PDFCompressorWindow()
                second.drop_zone.hide()
                self.addCleanup(second.drop_zone.deleteLater)
                self.addCleanup(second.deleteLater)
                self.assertTrue(second.keep_original.isChecked())

                second.keep_original.setChecked(False)
                third = self.module.PDFCompressorWindow()
                third.drop_zone.hide()
                self.addCleanup(third.drop_zone.deleteLater)
                self.addCleanup(third.deleteLater)
                self.assertFalse(third.keep_original.isChecked())


if __name__ == "__main__":
    unittest.main()
