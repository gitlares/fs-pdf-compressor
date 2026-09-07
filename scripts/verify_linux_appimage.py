#!/usr/bin/env python3
"""Exercise an actual AppImage using generated PDFs and an isolated X display.

Run under xvfb-run. No existing application process or user PDF is touched.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

from tests.test_core import _write_optional_content_pdf


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("appimage", type=Path, nargs="?")
    parser.add_argument("--snap", action="store_true", help="Test the installed fs-pdf-compressor Snap instead")
    args = parser.parse_args()
    if not args.snap and args.appimage is None:
        parser.error("provide an AppImage or --snap")
    records = []
    with tempfile.TemporaryDirectory(prefix="fs-pdf-packaged-test-", dir=Path.home()) as directory:
        root = Path(directory)
        for unavailable in (False, True):
            original = root / f"fs-pdf-test-{uuid.uuid4().hex}.pdf"
            _write_optional_content_pdf(original)
            before = original.read_bytes()
            environment = os.environ.copy()
            environment.update(XDG_CONFIG_HOME=str(root / "config"), QT_QPA_PLATFORM="xcb")
            if unavailable and not args.snap:
                # Exercise the real failure path: a deliberately nonexistent
                # session bus cannot provide a trash portal. Not a Snap test.
                environment.update(SNAP="platform-test", DBUS_SESSION_BUS_ADDRESS="unix:path=/nonexistent/fs-pdf-test-bus")
            else:
                environment.pop("SNAP", None)
            with tempfile.TemporaryFile(mode="w+b") as log:
                command = ["snap", "run", "fs-pdf-compressor", str(original)] if args.snap else [str(args.appimage.resolve()), "--appimage-extract-and-run", str(original)]
                if args.snap and unavailable:
                    # Break the application portal only AFTER snap-launcher
                    # has used the real session bus to establish its cgroup.
                    command = ["snap", "run", "--shell", "fs-pdf-compressor", "-c",
                               'export DBUS_SESSION_BUS_ADDRESS=unix:path=/nonexistent/fs-pdf-test-bus; exec "$SNAP/bin/fs-pdf-compressor" "$1"',
                               "fs-pdf-test", str(original)]
                process = subprocess.Popen(command, env=environment, stdout=log, stderr=log)
                try:
                    deadline = time.monotonic() + 60
                    while time.monotonic() < deadline:
                        if process.poll() is not None:
                            log.seek(0)
                            raise AssertionError(f"Application exited: {log.read().decode(errors='replace')}")
                        if original.exists() and original.read_bytes() != before:
                            break
                        time.sleep(0.1)
                    after = original.read_bytes()
                    assert len(after) < len(before), "Packaged application did not compress the input"
                    assert after.startswith(b"%PDF-") and b"%%EOF" in after[-1024:]
                    time.sleep(1)
                    assert process.poll() is None, "Application crashed after compression"
                    trash = Path.home() / ".local/share/Trash/files"
                    recovered = any(path.read_bytes() == before for path in trash.glob(original.stem + "*"))
                    if not args.snap:
                        assert recovered == (not unavailable), f"Unexpected trash result: {recovered}"
                    assert not list(root.glob(".fs-pdf-*.tmp")), "Temporary file leak"
                    subprocess.run(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=nullpage", str(original)], check=True, timeout=30)
                    records.append({"package": "snap" if args.snap else "appimage", "portal_unavailable": unavailable, "before": len(before), "after": len(after), "original_in_trash": recovered, "ghostscript_render": "passed"})
                finally:
                    # Only this test's process is stopped, after the output
                    # has settled; no killall or existing desktop app affected.
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
