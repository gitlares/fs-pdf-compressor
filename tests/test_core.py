# SPDX-License-Identifier: AGPL-3.0-or-later

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fs_pdf_compressor.core import (
    _ghostscript_command,
    compress_pdf,
    compressed_copy_path,
    expand_pdf_paths,
)


def _write_optional_content_pdf(path: Path) -> None:
    """Create a PDF whose blue artwork is visible on screen but not in print."""
    content = (
        b"0.94 0.94 0.94 rg 0 0 612 792 re f\n"
        b"/OC /ScreenArtwork BDC\n"
        b"0.15 0.35 0.85 rg 90 120 432 550 re f\n"
        b"EMC\n"
    )
    objects = [
        b"<</Type/Catalog/Pages 2 0 R/OCProperties<</OCGs[5 0 R]/D<</Name(Screen view)/BaseState/ON/ON[5 0 R]/Order[5 0 R]/AS[<</Event/View/Category[/View]/OCGs[5 0 R]>><</Event/Print/Category[/Print]/OCGs[5 0 R]>>]>>>>>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<</Properties<</ScreenArtwork 5 0 R>>>>/Contents 4 0 R>>",
        b"<</Length %d>>\nstream\n%s\nendstream" % (len(content), content),
        b"<</Type/OCG/Name(Screen artwork)/Usage<</View<</ViewState/ON>>/Print<</PrintState/OFF>>>>>>",
    ]
    payload = bytearray(b"%PDF-1.5\n% optional-content regression fixture\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(payload))
        payload.extend(f"{number} 0 obj\n".encode())
        payload.extend(body)
        payload.extend(b"\nendobj\n")
    payload.extend((b"% padding discarded by pdfwrite\n" * 2_000))
    xref_offset = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    payload.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode())
    payload.extend(
        f"trailer\n<</Size {len(objects) + 1}/Root 1 0 R>>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    )
    path.write_bytes(payload)


def _ppm_center_pixel(path: Path) -> tuple[int, int, int]:
    payload = path.read_bytes()
    position = 0
    tokens: list[bytes] = []
    while len(tokens) < 4:
        while position < len(payload) and payload[position : position + 1].isspace():
            position += 1
        if payload[position : position + 1] == b"#":
            position = payload.index(b"\n", position) + 1
            continue
        end = position
        while end < len(payload) and not payload[end : end + 1].isspace():
            end += 1
        tokens.append(payload[position:end])
        position = end
    while payload[position : position + 1].isspace():
        position += 1
    magic, width, height, maximum = tokens
    if magic != b"P6" or maximum != b"255":
        raise AssertionError("Unexpected PPM header")
    width_value = int(width)
    height_value = int(height)
    pixel_offset = position + ((height_value // 2) * width_value + width_value // 2) * 3
    return tuple(payload[pixel_offset : pixel_offset + 3])


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


class GhostscriptCommandTests(unittest.TestCase):
    def test_pdfwrite_preserves_optional_content_and_screen_appearance(self):
        command = _ghostscript_command("gs", "output.pdf", "input.pdf", "/ebook")

        self.assertIn("-dCompatibilityLevel=1.7", command)
        self.assertIn("-dPrinted=false", command)
        self.assertIn("-dWantsOptionalContent=true", command)
        self.assertIn("-dPreserveMarkedContent=true", command)

    def test_compression_keeps_screen_only_artwork(self):
        from fs_pdf_compressor.core import get_ghostscript_config

        gs_path, gs_environment = get_ghostscript_config()
        if not gs_path:
            self.skipTest("Ghostscript is not installed")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "layered.pdf"
            _write_optional_content_pdf(original)

            with mock.patch(
                "fs_pdf_compressor.core.get_ghostscript_config",
                return_value=(gs_path, gs_environment),
            ):
                _, metrics = compress_pdf(str(original), "/ebook", keep_original=True)

            self.assertIsNotNone(metrics)
            compressed = root / "layered compressed.pdf"
            rendered = root / "layered.ppm"
            result = subprocess.run(
                [
                    gs_path,
                    "-sDEVICE=ppmraw",
                    "-dPrinted=false",
                    "-r72",
                    "-dNOPAUSE",
                    "-dQUIET",
                    "-dBATCH",
                    f"-sOutputFile={rendered}",
                    str(compressed),
                ],
                env=gs_environment,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            red, green, blue = _ppm_center_pixel(rendered)
            self.assertGreater(blue, red + 50)
            self.assertGreater(blue, green + 50)


if __name__ == "__main__":
    unittest.main()
