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


if __name__ == "__main__":
    unittest.main()
