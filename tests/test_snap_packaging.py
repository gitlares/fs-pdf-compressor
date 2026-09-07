"""Packaging regressions supplement, but do not replace, confined Snap tests."""
from pathlib import Path
import unittest


class SnapPackagingTests(unittest.TestCase):
    def setUp(self):
        self.recipe = (Path(__file__).resolve().parents[1] / "snapcraft.yaml").read_text()

    def test_ghostscript_resources_are_available_at_compiled_in_paths(self):
        for resource in ("/usr/share/ghostscript", "/usr/share/fonts", "/usr/share/color/icc/ghostscript"):
            with self.subTest(resource=resource):
                self.assertIn(f"  {resource}:\n    bind: $SNAP{resource}", self.recipe)

    def test_wayland_client_runtime_is_staged(self):
        for package in ("libwayland-cursor0", "libwayland-egl1", "libwayland-server0"):
            self.assertIn(f"      - {package}\n", self.recipe)

    def test_package_stays_strict_and_checks_source_version(self):
        self.assertIn("confinement: strict\n", self.recipe)
        self.assertIn('test "$source_version" = "$CRAFT_PROJECT_VERSION"', self.recipe)


if __name__ == "__main__":
    unittest.main()
