# SPDX-License-Identifier: AGPL-3.0-or-later

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_linux


class LinuxDependencyBundleTests(unittest.TestCase):
    def test_copy_shared_libraries_keeps_host_glibc(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            system_runtime = root / "libc.so.6"
            portable_dependency = root / "libgs.so.9"
            system_runtime.touch()
            portable_dependency.touch()
            ldd_output = (
                f"libc.so.6 => {system_runtime} (0x0)\n"
                f"libgs.so.9 => {portable_dependency} (0x0)\n"
            )
            destination = root / "bundle"

            with patch.object(build_linux, "command_output", return_value=ldd_output):
                build_linux.copy_shared_libraries(root / "gs", destination)

            self.assertFalse((destination / system_runtime.name).exists())
            self.assertTrue((destination / portable_dependency.name).exists())

    def test_copy_shared_libraries_copies_transitive_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / "libqxcb.so"
            direct_dependency = root / "libQt6XcbQpa.so.6"
            transitive_dependency = root / "libxcb-icccm.so.4"
            for path in (plugin, direct_dependency, transitive_dependency):
                path.touch()
            destination = root / "bundle"

            def ldd_output(*args: str) -> str:
                target = Path(args[-1])
                if target == plugin:
                    return f"libQt6XcbQpa.so.6 => {direct_dependency} (0x0)\\n"
                if target == direct_dependency:
                    return f"libxcb-icccm.so.4 => {transitive_dependency} (0x0)\\n"
                return ""

            with patch.object(build_linux, "command_output", side_effect=ldd_output):
                build_linux.copy_shared_libraries(plugin, destination)

            self.assertTrue((destination / direct_dependency.name).exists())
            self.assertTrue((destination / transitive_dependency.name).exists())

    def test_bundle_qt_platform_dependencies_uses_qt_library_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            resources = Path(directory)
            plugin = resources / "PySide6" / "Qt" / "plugins" / "platforms" / "libqxcb.so"
            plugin.parent.mkdir(parents=True)
            plugin.touch()

            with patch.object(build_linux, "copy_shared_libraries") as copy_libraries:
                build_linux.bundle_qt_platform_dependencies(resources)

            copy_libraries.assert_called_once_with(
                plugin,
                resources / "PySide6" / "Qt" / "lib",
            )

    def test_bundle_qt_platform_dependencies_requires_xcb_plugin(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "X11 platform plugin was not found"):
                build_linux.bundle_qt_platform_dependencies(Path(directory))


if __name__ == "__main__":
    unittest.main()
