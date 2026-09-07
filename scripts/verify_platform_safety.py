#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Opt-in real Ghostscript/trash/UI smoke test using generated PDFs only.

Run from the repository: python -m scripts.verify_platform_safety [--qt]
Generated originals remain in the system trash and are identified in output.
"""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import uuid
from unittest import mock

from fs_pdf_compressor import core
from fs_pdf_compressor.version import APP_VERSION
from tests.test_core import _write_optional_content_pdf


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qt", action="store_true")
    parser.add_argument("--portal", action="store_true")
    parser.add_argument("--allow-unavailable-trash", action="store_true",
                        help="Verify best-effort replacement without requiring trash recovery")
    args = parser.parse_args()
    application = None
    if args.qt or args.portal:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6 import QtWidgets
        application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    if args.portal:
        os.environ["SNAP"] = "platform-test"
    with tempfile.TemporaryDirectory(prefix="fs-pdf-verification-", dir=Path.home()) as directory:
        root = Path(directory)
        records = []
        for label, profile, _ in core.QUALITY_PROFILES:
            for keep in (True, False):
                recovered = None
                original = root / f"fs-pdf-test-{uuid.uuid4().hex}.pdf"
                _write_optional_content_pdf(original)
                before = original.read_bytes()
                destinations = []
                recycle = core.move_to_system_trash
                def record_trash(path):
                    destination = recycle(path)
                    if destination:
                        destinations.append(Path(destination))
                    return destination
                with mock.patch.object(core, "move_to_system_trash", side_effect=record_trash):
                    status, metric = core.compress_pdf(str(original), profile, keep)
                assert metric is not None, status
                if keep:
                    assert original.read_bytes() == before
                    compressed = root / (original.stem + " compressed.pdf")
                    assert core._valid_pdf_output(compressed)
                else:
                    assert original.read_bytes() != before
                    trash_directory = Path.home() / (".Trash" if sys.platform == "darwin" else ".local/share/Trash/files")
                    candidates = destinations or list(trash_directory.glob(original.stem + "*"))
                    recovered = any(path.read_bytes() == before for path in candidates)
                    if not args.allow_unavailable_trash:
                        assert recovered, f"Original not recoverable in {trash_directory}"
                records.append({"profile": label, "keep_original": keep, "status": status, "trash_recovery_confirmed": recovered})
        if args.qt:
            from PySide6 import QtCore
            import linux_app
            window = linux_app.PDFCompressorWindow()
            window.keep_original.setChecked(True)
            original = root / "async-folder.pdf"
            _write_optional_content_pdf(original)
            window.show()
            assert window.start_paths([str(root)])
            deadline = time.monotonic() + 45
            ticks = []
            timer = QtCore.QTimer()
            timer.timeout.connect(lambda: ticks.append(True))
            timer.start(10)
            while window.processing and time.monotonic() < deadline:
                application.processEvents()
                time.sleep(0.005)
            timer.stop()
            assert not window.processing, "Batch did not finish"
            assert window.thread is None and window.discovery_thread is None
            assert any(window.metrics), window.status_label.text()
            assert ticks, "Qt event loop was unresponsive"
            window.drop_zone.hide()
            window.hide()
            window.drop_zone.deleteLater()
            window.deleteLater()
        confinement = None
        if sys.platform == "linux":
            try:
                confinement = Path("/proc/self/attr/current").read_text().strip()
            except PermissionError:
                confinement = "kernel profile read restricted"
        print(json.dumps({"version": APP_VERSION, "core_path": core.__file__, "snap": os.environ.get("SNAP"), "confinement": confinement, "platform": sys.platform, "portal": args.portal, "qt": args.qt, "results": records}, indent=2))


if __name__ == "__main__":
    main()
