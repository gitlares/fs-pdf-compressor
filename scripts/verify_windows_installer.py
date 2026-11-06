# SPDX-License-Identifier: AGPL-3.0-or-later
"""Disposable Windows CI install/upgrade test; never run on a user's desktop."""

from __future__ import annotations

import argparse
import base64
import ctypes
import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from fs_pdf_compressor import windows_update
from fs_pdf_compressor.version import WINDOWS_APP_VERSION


def digest(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def native_probe(case, installer, dll_path, output):
    """Use the real WinSparkle parser/downloader/Ed25519 verification on loopback."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    root = output.parent / ('probe-' + case)
    root.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    public = base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
    payload = root / installer.name
    shutil.copy2(installer, payload)
    signature = base64.b64encode(key.sign(payload.read_bytes())).decode()
    if case == 'tampered':
        with payload.open('ab') as stream:
            stream.write(b'CI tamper test')
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)
        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}'
    ns = 'http://www.andymatuschak.org/xml-namespaces/sparkle'
    ET.register_namespace('sparkle', ns)
    rss = ET.Element('rss', {'version': '2.0'})
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text = 'Disposable CI update'
    if case != 'no-update':
        item = ET.SubElement(channel, 'item')
        ET.SubElement(item, 'title').text = WINDOWS_APP_VERSION
        ET.SubElement(item, 'enclosure', {
            'url': url + '/' + payload.name, 'length': str(payload.stat().st_size),
            'type': 'application/octet-stream', f'{{{ns}}}version': WINDOWS_APP_VERSION,
            f'{{{ns}}}os': 'windows-x64', f'{{{ns}}}edSignature': signature,
        })
    ET.ElementTree(rss).write(root / 'feed.xml', encoding='utf-8', xml_declaration=True)
    dll = ctypes.CDLL(str(dll_path.resolve()))
    dll.win_sparkle_set_registry_path.argtypes = [ctypes.c_char_p]
    dll.win_sparkle_set_registry_path.restype = None
    dll.win_sparkle_set_registry_path(f'Software\\FSPDFCompressorCI\\{uuid.uuid4().hex}'.encode())
    dll.win_sparkle_set_automatic_check_for_updates.argtypes = [ctypes.c_int]
    dll.win_sparkle_set_automatic_check_for_updates.restype = None
    dll.win_sparkle_set_automatic_check_for_updates(0)
    done = threading.Event()
    result = {'case': case, 'download_verified': False, 'error': False, 'no_update': False}
    void_callback = ctypes.CFUNCTYPE(None)
    install_callback_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_wchar_p)
    def error():
        result['error'] = True
        done.set()
    def no_update():
        result['no_update'] = True
        done.set()
    def installer_ready(path):
        try:
            # This native callback is reached only after native signature validation.
            copied = output.parent / 'native-verified-setup.exe'
            shutil.copy2(path, copied)
            result['download_verified'] = digest(copied) == digest(installer)
            result['installer_path'] = str(copied)
        except Exception as exc:
            result['callback_failure'] = type(exc).__name__
        done.set()
        return 1  # The test handles the verified payload itself, after cleanup.
    callbacks = [void_callback(error), void_callback(no_update), install_callback_type(installer_ready)]
    for name, callback in zip(['set_error_callback', 'set_did_not_find_update_callback', 'set_user_run_installer_callback'], callbacks):
        function = getattr(dll, 'win_sparkle_' + name)
        function.argtypes, function.restype = [type(callback)], None
        function(callback)
    with mock.patch.object(windows_update, 'PUBLIC_KEY', public), mock.patch.object(windows_update, 'FEED_URL', url + '/feed.xml'), mock.patch.object(windows_update, 'APP_VERSION', '1.0.16'):
        updater = windows_update.WindowsUpdater(lambda: None, dll)
    # WindowsUpdater configures its own error callback; use the test observer.
    dll.win_sparkle_set_error_callback(callbacks[0])
    updater.set_busy(False)
    updater.start()
    try:
        dll.win_sparkle_check_update_with_ui_and_install.argtypes = []
        dll.win_sparkle_check_update_with_ui_and_install.restype = None
        dll.win_sparkle_check_update_with_ui_and_install()
        if not done.wait(120):
            raise RuntimeError(f'Native {case} test timed out')
        if case == 'valid':
            assert result['download_verified'] and not result['error'], result
        elif case == 'tampered':
            assert result['error'] and not result['download_verified'], result
        else:
            assert result['no_update'] and not result['error'], result
    finally:
        updater.cleanup()
        server.shutdown()
        server.server_close()
        output.write_text(json.dumps(result, indent=2))


def install(installer, directory, log):
    command = [str(installer.resolve()), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', f'/DIR={directory}', f'/LOG={log}']
    result = subprocess.run(command, timeout=180)
    if result.returncode != 0:
        raise RuntimeError(f'Inno Setup failed: exit {result.returncode}')


def verify_candidate(installer, portable, output):
    import winreg
    output.mkdir(parents=True, exist_ok=True)
    directory = output / 'installed'
    old = output / 'previous-1.0.16-setup.exe'
    prefix = 'https://github.com/gitlares/fs-pdf-compressor/releases/download/v1.0.16/'
    name = 'FS-PDF-Compressor-1.0.16-windows-x86_64-setup.exe'
    urllib.request.urlretrieve(prefix + name, old)
    with urllib.request.urlopen(prefix + name + '.sha256', timeout=30) as response:
        expected = response.read(4096).decode().split()[0]
    assert digest(old) == expected, 'Previous installer checksum mismatch'
    install(old, directory, output / 'install-previous.log')
    # Silent installers may launch the app: stop only the disposable CI app.
    stop_test_app(directory)
    settings_key = windows_update.INSTALL_REGISTRY_KEY
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, settings_key) as key:
        winreg.SetValueEx(key, 'keepOriginal', 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, 'dropZoneEnabled', 0, winreg.REG_DWORD, 0)
    runtime = portable / 'FS PDF Compressor' / '_internal' / 'WinSparkle.dll'
    for case in ['no-update', 'tampered', 'valid']:
        subprocess.run([sys.executable, '-m', 'scripts.verify_windows_installer', '--probe', case, '--installer', str(installer), '--dll', str(runtime), '--output', str(output / (case + '.json'))], check=True, timeout=150)
    # Upgrade using the exact payload downloaded and authenticated by WinSparkle.
    install(output / 'native-verified-setup.exe', directory, output / 'upgrade.log')
    executable = directory / 'FS PDF Compressor.exe'
    assert digest(executable) == digest(portable / 'FS PDF Compressor' / executable.name)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, settings_key) as key:
        assert winreg.QueryValueEx(key, 'keepOriginal')[0] == 1
        assert winreg.QueryValueEx(key, 'dropZoneEnabled')[0] == 0
        assert Path(winreg.QueryValueEx(key, 'InstallDir')[0]).resolve() == directory.resolve()
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Classes\SystemFileAssociations\.pdf\shell\CompressWithFSPDFCompressor\command') as key:
        assert str(executable) in winreg.QueryValueEx(key, '')[0]
    # Validate the frozen app loads Qt/WinSparkle and remains running after launch.
    stop_test_app(directory)
    process = subprocess.Popen([str(executable)])
    try:
        time.sleep(8)
        assert process.poll() is None, 'Installed application exited during startup'
    finally:
        process.terminate()
        process.wait(timeout=20)
    for path in output.glob('probe-*/*setup.exe'):
        path.unlink()  # Keep reports, not redundant large installers.
    for path in [old, output / 'native-verified-setup.exe']:
        path.unlink()
    report = {
        'version': WINDOWS_APP_VERSION, 'previous_version': '1.0.16',
        'native_signed_download': True, 'native_tamper_rejection': True,
        'native_no_update': True, 'silent_upgrade': True,
        'preferences_preserved': True, 'explorer_integration': True,
        'installed_app_launch': True,
        'limitations': ['Test-only signing identity and loopback feed', 'Update approval dialog and desktop drag/drop not manually reviewed'],
    }
    (output / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


def stop_test_app(directory):
    # Match executable path rather than killing unrelated applications by name.
    executable = str((directory / 'FS PDF Compressor.exe').resolve()).replace("'", "''")
    script = f"Get-CimInstance Win32_Process | Where-Object {{ $_.ExecutablePath -eq '{executable}' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}"
    subprocess.run(['powershell', '-NoProfile', '-Command', script], check=True, timeout=30)


def main():
    if sys.platform != 'win32' or os.environ.get('GITHUB_ACTIONS') != 'true':
        raise RuntimeError('This installation test is restricted to disposable GitHub Windows runners')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installer', required=True, type=Path)
    parser.add_argument('--portable', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--probe', choices=['valid', 'tampered', 'no-update'])
    parser.add_argument('--dll', type=Path)
    args = parser.parse_args()
    if args.probe:
        native_probe(args.probe, args.installer, args.dll, args.output)
    else:
        verify_candidate(args.installer, args.portable, args.output)


if __name__ == '__main__':
    main()
