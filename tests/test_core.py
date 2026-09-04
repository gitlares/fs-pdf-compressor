# SPDX-License-Identifier: AGPL-3.0-or-later

import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

from fs_pdf_compressor.core import (
    _error_output_tail,
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


def _pdf_stream(dictionary: bytes, payload: bytes) -> bytes:
    return (
        b"<<"
        + dictionary
        + f"/Length {len(payload)}>>\nstream\n".encode()
        + payload
        + b"\nendstream"
    )


def _write_mixed_transparency_pdf(path: Path) -> None:
    """Create RGB artwork inside a masked CMYK transparency group."""
    page_content = b"q /Fm0 Do Q"
    form_content = b"/GS0 gs q 300 0 0 300 0 0 cm /Im0 Do Q"
    mask_content = b"q 300 0 0 300 0 0 cm /MaskImage Do Q"
    image = bytes(
        [
            255,
            80,
            20,
            20,
            180,
            255,
            30,
            220,
            70,
            240,
            40,
            180,
        ]
    )
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 300]/Resources"
        b"<</XObject<</Fm0 4 0 R>>>>/Contents 5 0 R>>",
        _pdf_stream(
            b"/Type/XObject/Subtype/Form/BBox[0 0 300 300]"
            b"/Group<</Type/Group/S/Transparency/CS/DeviceCMYK/I false/K false>>"
            b"/Resources<</ExtGState<</GS0 6 0 R>>/XObject<</Im0 7 0 R>>>>",
            form_content,
        ),
        _pdf_stream(b"", page_content),
        b"<</Type/ExtGState/AIS false/BM/Normal/ca 1/CA 1/SMask"
        b"<</Type/Mask/S/Luminosity/G 9 0 R/BC[1]>>>>",
        _pdf_stream(
            b"/Type/XObject/Subtype/Image/Width 2/Height 2/ColorSpace/DeviceRGB"
            b"/BitsPerComponent 8/Filter/FlateDecode/SMask 8 0 R",
            zlib.compress(image),
        ),
        _pdf_stream(
            b"/Type/XObject/Subtype/Image/Width 2/Height 2/ColorSpace/DeviceGray"
            b"/BitsPerComponent 8/Filter/FlateDecode",
            zlib.compress(bytes([255, 255, 255, 255])),
        ),
        _pdf_stream(
            b"/Type/XObject/Subtype/Form/BBox[0 0 300 300]"
            b"/Group<</Type/Group/S/Transparency/CS/DeviceGray/I false/K false>>"
            b"/Resources<</XObject<</MaskImage 10 0 R>>>>",
            mask_content,
        ),
        _pdf_stream(
            b"/Type/XObject/Subtype/Image/Width 2/Height 2/ColorSpace/DeviceGray"
            b"/BitsPerComponent 8/Filter/FlateDecode",
            zlib.compress(bytes([80, 160, 220, 255])),
        ),
    ]
    payload = bytearray(b"%PDF-1.7\n% mixed-transparency regression fixture\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(payload))
        payload.extend(f"{number} 0 obj\n".encode())
        payload.extend(body)
        payload.extend(b"\nendobj\n")
    xref_offset = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    payload.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode())
    payload.extend(
        f"trailer\n<</Size {len(objects) + 1}/Root 1 0 R>>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode()
    )
    path.write_bytes(payload)


def _ppm_pixel(path: Path, x_fraction: float, y_fraction: float) -> tuple[int, int, int]:
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
    x = min(width_value - 1, round(width_value * x_fraction))
    y = min(height_value - 1, round(height_value * y_fraction))
    pixel_offset = position + (y * width_value + x) * 3
    return tuple(payload[pixel_offset : pixel_offset + 3])


def _ppm_center_pixel(path: Path) -> tuple[int, int, int]:
    return _ppm_pixel(path, 0.5, 0.5)


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


class ProcessOutputTests(unittest.TestCase):
    def test_error_output_tail_is_bounded(self):
        with tempfile.SpooledTemporaryFile(max_size=16, mode="w+b") as output:
            output.write(b"x" * 64 + b"final diagnostic")

            self.assertEqual(_error_output_tail(output, limit=16), "final diagnostic")

    def test_compression_discards_stdout_and_spools_stderr(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "original.pdf"
            original.write_bytes(b"original payload")
            received = {}

            def fail_with_diagnostic(command, **kwargs):
                received.update(kwargs)
                kwargs["stderr"].write(b"bad input")
                return subprocess.CompletedProcess(command, 1)

            with (
                mock.patch(
                    "fs_pdf_compressor.core.get_ghostscript_config",
                    return_value=("gs", {}),
                ),
                mock.patch(
                    "fs_pdf_compressor.core.subprocess.run",
                    side_effect=fail_with_diagnostic,
                ),
            ):
                status, metrics = compress_pdf(str(original), "/ebook", keep_original=False)

            self.assertEqual(status, "original.pdf — compression failed")
            self.assertIsNone(metrics)
            self.assertIs(received["stdout"], subprocess.DEVNULL)
            self.assertNotIn("capture_output", received)


class GhostscriptCommandTests(unittest.TestCase):
    def test_pdfwrite_preserves_optional_content_and_screen_appearance(self):
        command = _ghostscript_command("gs", "output.pdf", "input.pdf", "/ebook")

        self.assertIn("-dCompatibilityLevel=1.7", command)
        self.assertIn("-dPrinted=false", command)
        self.assertIn("-dWantsOptionalContent=true", command)
        self.assertIn("-dPreserveMarkedContent=true", command)

    def test_pdfwrite_preserves_mixed_color_transparency(self):
        for profile in ("/prepress", "/ebook", "/screen"):
            with self.subTest(profile=profile):
                command = _ghostscript_command("gs", "output.pdf", "input.pdf", profile)

                self.assertIn("-sColorConversionStrategy=LeaveColorUnchanged", command)
                self.assertGreater(
                    command.index("-sColorConversionStrategy=LeaveColorUnchanged"),
                    command.index(f"-dPDFSETTINGS={profile}"),
                )

    def test_compression_keeps_masked_artwork_in_mixed_color_transparency(self):
        from fs_pdf_compressor.core import get_ghostscript_config

        gs_path, gs_environment = get_ghostscript_config()
        if not gs_path:
            self.skipTest("Ghostscript is not installed")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "mixed-transparency.pdf"
            _write_mixed_transparency_pdf(original)

            for label, profile in (
                ("preserve", "/prepress"),
                ("balanced", "/ebook"),
                ("maximum", "/screen"),
            ):
                with self.subTest(profile=profile):
                    compressed = root / f"{label}.pdf"
                    rendered = root / f"{label}.ppm"
                    compression = subprocess.run(
                        _ghostscript_command(
                            gs_path,
                            str(compressed),
                            str(original),
                            profile,
                        ),
                        env=gs_environment,
                        capture_output=True,
                    )
                    self.assertEqual(
                        compression.returncode,
                        0,
                        compression.stderr.decode(errors="replace"),
                    )
                    rendering = subprocess.run(
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
                    self.assertEqual(
                        rendering.returncode,
                        0,
                        rendering.stderr.decode(errors="replace"),
                    )
                    top_left = _ppm_pixel(rendered, 0.25, 0.25)
                    top_right = _ppm_pixel(rendered, 0.75, 0.25)
                    bottom_left = _ppm_pixel(rendered, 0.25, 0.75)
                    bottom_right = _ppm_pixel(rendered, 0.75, 0.75)
                    self.assertGreater(top_left[0], top_left[1] + 40)
                    self.assertGreater(top_left[0], top_left[2] + 40)
                    self.assertGreater(top_right[2], top_right[0] + 40)
                    self.assertGreater(bottom_left[1], bottom_left[0] + 40)
                    self.assertGreater(bottom_left[1], bottom_left[2] + 40)
                    self.assertGreater(bottom_right[0], bottom_right[1] + 40)
                    self.assertGreater(bottom_right[2], bottom_right[1] + 40)

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

    def test_compress_pdf_replaces_only_after_a_smaller_result(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "original.pdf"
            original.write_bytes(b"original payload")

            def write_smaller(command, **_kwargs):
                output = next(value for value in command if value.startswith("-sOutputFile="))
                Path(output.removeprefix("-sOutputFile=")).write_bytes(b"small")
                return subprocess.CompletedProcess(command, 0, b"", b"")

            with (
                mock.patch(
                    "fs_pdf_compressor.core.get_ghostscript_config",
                    return_value=("gs", {}),
                ),
                mock.patch("fs_pdf_compressor.core.subprocess.run", side_effect=write_smaller),
            ):
                status, metrics = compress_pdf(str(original), "/ebook", keep_original=False)

            self.assertEqual(original.read_bytes(), b"small")
            self.assertIn("original.pdf", status)
            self.assertEqual(metrics, {"original_size": 16, "saved_size": 11})
            self.assertFalse(Path(f"{original}.temp.pdf").exists())

    def test_compress_pdf_keeps_original_when_output_is_not_smaller(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "original.pdf"
            original.write_bytes(b"original payload")

            def write_larger(command, **_kwargs):
                output = next(value for value in command if value.startswith("-sOutputFile="))
                Path(output.removeprefix("-sOutputFile=")).write_bytes(b"larger output than input")
                return subprocess.CompletedProcess(command, 0, b"", b"")

            with (
                mock.patch(
                    "fs_pdf_compressor.core.get_ghostscript_config",
                    return_value=("gs", {}),
                ),
                mock.patch("fs_pdf_compressor.core.subprocess.run", side_effect=write_larger),
            ):
                status, metrics = compress_pdf(str(original), "/ebook", keep_original=False)

            self.assertEqual(original.read_bytes(), b"original payload")
            self.assertEqual(status, "original.pdf — no size reduction")
            self.assertIsNone(metrics)
            self.assertFalse(Path(f"{original}.temp.pdf").exists())

    def test_compress_pdf_keeps_original_and_cleans_temp_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "original.pdf"
            original.write_bytes(b"original payload")

            def fail_after_partial_output(command, **_kwargs):
                output = next(value for value in command if value.startswith("-sOutputFile="))
                Path(output.removeprefix("-sOutputFile=")).write_bytes(b"partial")
                return subprocess.CompletedProcess(command, 1, b"", b"bad input")

            with (
                mock.patch(
                    "fs_pdf_compressor.core.get_ghostscript_config",
                    return_value=("gs", {}),
                ),
                mock.patch(
                    "fs_pdf_compressor.core.subprocess.run",
                    side_effect=fail_after_partial_output,
                ),
            ):
                status, metrics = compress_pdf(str(original), "/ebook", keep_original=False)

            self.assertEqual(original.read_bytes(), b"original payload")
            self.assertEqual(status, "original.pdf — compression failed")
            self.assertIsNone(metrics)
            self.assertFalse(Path(f"{original}.temp.pdf").exists())


if __name__ == "__main__":
    unittest.main()
