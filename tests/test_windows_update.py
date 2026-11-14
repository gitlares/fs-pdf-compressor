# SPDX-License-Identifier: AGPL-3.0-or-later
"""Regression coverage for authenticated updates and safe native shutdown."""

import base64
import importlib.util
import tempfile
import unittest
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

from fs_pdf_compressor import windows_update
import build_windows


class WindowsUpdaterTests(unittest.TestCase):
    def setUp(self):
        self.dll = mock.Mock()
        self.dll.win_sparkle_set_eddsa_public_key.return_value = 1
        self.shutdown = mock.Mock()
        self.updater = windows_update.WindowsUpdater(self.shutdown, self.dll)

    def test_busy_app_rejects_installer_and_idle_app_reserves_only_once(self):
        self.assertEqual(self.updater._can_shutdown_callback(), 0)
        self.updater.set_busy(False)
        with ThreadPoolExecutor(max_workers=4) as pool:
            decisions = list(pool.map(lambda _: self.updater._can_shutdown_callback(), range(4)))
        self.assertEqual(sum(decisions), 1)
        self.assertFalse(self.updater.begin_work())
        self.updater._shutdown_callback()
        self.shutdown.assert_called_once()

    def test_new_batch_prevents_installation(self):
        self.updater.set_busy(False)
        self.assertTrue(self.updater.begin_work())
        self.assertEqual(self.updater._can_shutdown_callback(), 0)

    def test_native_failure_releases_installation_reservation(self):
        self.updater.set_busy(False)
        self.assertEqual(self.updater._can_shutdown_callback(), 1)
        self.updater._error_callback()
        self.assertTrue(self.updater.begin_work())

    def test_invalid_public_key_never_initializes_updater(self):
        self.dll.win_sparkle_set_eddsa_public_key.return_value = 0
        with self.assertRaises(RuntimeError):
            windows_update.WindowsUpdater(self.shutdown, self.dll)
        self.dll.win_sparkle_init.assert_not_called()

    def test_lifecycle_is_idempotent_and_preserves_check_preference(self):
        self.updater.start()
        self.updater.start()
        self.updater.check()
        self.updater.cleanup()
        self.updater.cleanup()
        self.dll.win_sparkle_init.assert_called_once()
        self.dll.win_sparkle_cleanup.assert_called_once()
        self.dll.win_sparkle_check_update_with_ui.assert_called_once()
        self.dll.win_sparkle_set_automatic_check_for_updates.assert_not_called()

    def test_windows_revision_does_not_change_shared_product_version(self):
        from fs_pdf_compressor.version import APP_VERSION, WINDOWS_APP_VERSION
        self.assertEqual(WINDOWS_APP_VERSION.rsplit('.', 1)[0], APP_VERSION)
        self.assertEqual(build_windows.APP_VERSION, WINDOWS_APP_VERSION)
        self.dll.win_sparkle_set_app_details.assert_called_once_with(
            'gitlares', 'FS PDF Compressor', WINDOWS_APP_VERSION)

    def test_portable_directory_cannot_be_updated_as_installed_app(self):
        registry = mock.Mock()
        registry.OpenKey.return_value.__enter__ = mock.Mock(return_value=object())
        registry.OpenKey.return_value.__exit__ = mock.Mock(return_value=False)
        registry.QueryValueEx.return_value = (str(Path('/installed')), 1)
        with mock.patch.dict('sys.modules', {'winreg': registry}), mock.patch.object(windows_update.sys, 'platform', 'win32'), mock.patch.object(windows_update.sys, 'frozen', True, create=True), mock.patch.object(windows_update.sys, 'executable', '/portable/app.exe'):
            self.assertFalse(windows_update.is_installed_application())
            with mock.patch.object(windows_update.sys, 'executable', '/installed/app.exe'):
                self.assertTrue(windows_update.is_installed_application())

    def test_untrusted_runtime_archive_is_rejected_before_bundling(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / build_windows.APP_NAME
            cache.mkdir()
            archive = cache / f'WinSparkle-{windows_update.WINSPARKLE_VERSION}.zip'
            archive.write_bytes(b'tampered runtime')
            with mock.patch.dict('os.environ', {'LOCALAPPDATA': directory}):
                with self.assertRaisesRegex(RuntimeError, 'checksum'):
                    build_windows.bundle_winsparkle(root / 'resources')
            self.assertFalse((root / 'resources/WinSparkle.dll').exists())
            self.assertFalse(archive.exists())


@unittest.skipUnless(importlib.util.find_spec('cryptography'), 'Release signing environment required')
class WindowsAppcastTests(unittest.TestCase):
    def test_windows_revisions_have_a_dedicated_release_tag(self):
        from scripts.generate_windows_appcast import release_tag
        self.assertEqual(release_tag('1.0.16.1'), 'v1.0.16.1-windows')
        self.assertEqual(release_tag('1.0.17'), 'v1.0.17')
        with self.assertRaises(ValueError):
            release_tag('1.0.16+windows.1')

    def test_signed_installer_tampering_and_wrong_identity_are_rejected(self):
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        from scripts import generate_windows_appcast as generator
        key = Ed25519PrivateKey.generate()
        public = base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
        with tempfile.TemporaryDirectory() as directory:
            installer = Path(directory) / 'FS-PDF-Compressor-1.0.16.1-windows-x86_64-setup.exe'
            installer.write_bytes(b'installer contents')
            feed = Path(directory) / 'feed.xml'
            feed.write_text('<rss version="2.0"><channel><title>Windows</title></channel></rss>')
            signature = base64.b64encode(key.sign(installer.read_bytes())).decode()
            with mock.patch.object(generator, 'PUBLIC_KEY', public):
                generator.update_feed(feed, installer, '1.0.16.1', signature)
                generator.update_feed(feed, installer, '1.0.16.1', signature)
                self.assertEqual(len(ET.parse(feed).findall('.//item')), 1)
                enclosure = ET.parse(feed).find('.//enclosure')
                self.assertEqual(enclosure.get(f'{{{generator.SPARKLE}}}os'), 'windows-x64')
                self.assertIn('/v1.0.16.1-windows/', enclosure.get('url'))
                self.assertIn('/NORESTART', enclosure.get(f'{{{generator.SPARKLE}}}installerArguments'))
                before = feed.read_bytes()
                installer.write_bytes(b'tampered installer')
                with self.assertRaises(InvalidSignature):
                    generator.update_feed(feed, installer, '1.0.16.1', signature)
                self.assertEqual(feed.read_bytes(), before)
                installer.write_bytes(b'installer contents')
            with self.assertRaises(InvalidSignature):
                generator.update_feed(feed, installer, '1.0.16.1', signature)
            self.assertEqual(feed.read_bytes(), before)


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'Qt environment required')
class WindowsUpdateLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6 import QtWidgets
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        from PySide6 import QtCore
        import windows_app
        self.module = windows_app
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        old_format = QtCore.QSettings.defaultFormat()
        QtCore.QSettings.setDefaultFormat(QtCore.QSettings.IniFormat)
        QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, self.directory.name)
        self.addCleanup(QtCore.QSettings.setDefaultFormat, old_format)
        self.window = windows_app.WindowsPDFCompressorWindow()
        self.window.drop_zone.hide()
        self.addCleanup(self.window.drop_zone.deleteLater)
        self.addCleanup(self.window.deleteLater)
        dll = mock.Mock()
        dll.win_sparkle_set_eddsa_public_key.return_value = 1
        self.window._windows_updater = windows_update.WindowsUpdater(self.window.update_shutdown_requested.emit, dll)

    def test_discovery_and_queued_explorer_paths_block_installation(self):
        updater = self.window._windows_updater
        self.window.discovery_thread = object()
        self.window._refresh_updater_busy()
        self.assertEqual(updater._can_shutdown_callback(), 0)
        self.window.discovery_thread = None
        self.window.queue_external_paths(['/test.pdf'])
        self.window._refresh_updater_busy()
        self.assertEqual(updater._can_shutdown_callback(), 0)
        self.window._external_paths_timer.stop()

    def test_install_reservation_blocks_new_discovery_and_repeat_compression(self):
        updater = self.window._windows_updater
        self.window._refresh_updater_busy()
        self.assertEqual(updater._can_shutdown_callback(), 1)
        self.assertFalse(self.window.start_paths(['/test.pdf']))
        self.window.start_compression()
        self.assertIsNone(self.window.thread)
        self.assertIsNone(self.window.discovery_thread)
        self.window.queue_external_paths(['/test.pdf'])
        self.assertEqual(self.window._external_paths, [])

    def test_native_shutdown_is_queued_to_the_qt_main_thread(self):
        with mock.patch.object(self.window, 'request_quit') as quit_app:
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(self.window._windows_updater._shutdown_callback).result()
            quit_app.assert_not_called()
            self.app.processEvents()
            quit_app.assert_called_once()

    def test_manual_check_uses_native_updater(self):
        self.window.check_for_updates()
        self.window._windows_updater._dll.win_sparkle_check_update_with_ui.assert_called_once()

    def test_about_displays_windows_revision(self):
        with mock.patch.object(self.module.QtWidgets.QMessageBox, 'about') as about:
            self.window.show_about()
        self.assertIn('1.0.16.1', about.call_args.args[2])


if __name__ == '__main__':
    unittest.main()
