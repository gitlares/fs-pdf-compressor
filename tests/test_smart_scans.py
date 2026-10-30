# SPDX-License-Identifier: AGPL-3.0-or-later

import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, NullObject

from fs_pdf_compressor.smart_scans import (
    _bilevel_scan_image,
    _looks_like_page_scan,
    preprocess_smart_scans,
)


def _document_scan(size=(1800, 2400), mode="L") -> Image.Image:
    image = Image.new(mode, size, "white")
    draw = ImageDraw.Draw(image)
    for y in range(240, 2050, 80):
        draw.rectangle((180, y, 1450, y + 18), fill="black")
    draw.rectangle((180, 120, 980, 165), fill="black")
    return image


def _write_text_pdf(path: Path) -> None:
    content = b"BT /F1 18 Tf 72 720 Td (Selectable text) Tj ET"
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<</Font<</F1 5 0 R>>>>/Contents 4 0 R>>",
        b"<</Length %d>>\nstream\n%s\nendstream" % (len(content), content),
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    payload = bytearray(b"%PDF-1.4\n")
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
        f"trailer\n<</Size {len(objects) + 1}/Root 1 0 R>>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    )
    path.write_bytes(payload)


class SmartScanClassificationTests(unittest.TestCase):
    def test_accepts_large_page_shaped_monochrome_document(self):
        self.assertTrue(_looks_like_page_scan(_document_scan(), (595, 842)))

    def test_rejects_grayscale_photograph(self):
        photo = Image.new("L", (1800, 2400))
        photo.putdata(
            [round(255 * x / 1799) for _y in range(2400) for x in range(1800)]
        )

        self.assertFalse(_looks_like_page_scan(photo, (595, 842)))

    def test_rejects_even_a_small_deliberate_colour_mark(self):
        image = _document_scan(mode="RGB")
        ImageDraw.Draw(image).rectangle((100, 100, 119, 119), fill=(210, 30, 30))

        self.assertFalse(_looks_like_page_scan(image, (595, 842)))

    def test_rejects_a_small_faint_gray_annotation(self):
        image = _document_scan(mode="RGB")
        ImageDraw.Draw(image).rectangle((100, 100, 119, 119), fill=(225, 225, 225))

        self.assertFalse(_looks_like_page_scan(image, (595, 842)))

    def test_rejects_faint_gray_text(self):
        for gray in (230, 235, 240, 245):
            with self.subTest(gray=gray):
                image = _document_scan(mode="RGB")
                ImageDraw.Draw(image).text(
                    (180, 40),
                    "PAID 123",
                    font=ImageFont.load_default(size=64),
                    fill=(gray, gray, gray),
                )

                self.assertFalse(_looks_like_page_scan(image, (595, 842)))

    def test_rejects_a_grayscale_gradient_patch(self):
        image = _document_scan(mode="RGB")
        patch = Image.new("L", (240, 240))
        patch.putdata([x for _y in range(240) for x in range(240)])
        image.paste(patch.convert("RGB"), (100, 100))

        self.assertFalse(_looks_like_page_scan(image, (595, 842)))

    def test_allows_isolated_near_threshold_scan_noise(self):
        image = _document_scan(mode="RGB")
        draw = ImageDraw.Draw(image)
        for coordinate in range(100, 1700, 40):
            draw.point((coordinate, 100), fill=(225, 225, 225))
            draw.point((coordinate, 2200), fill=(225, 225, 225))

        self.assertTrue(_looks_like_page_scan(image, (595, 842)))

    def test_rejects_small_or_non_page_shaped_images(self):
        self.assertFalse(
            _looks_like_page_scan(_document_scan((800, 1000)), (595, 842))
        )
        self.assertFalse(
            _looks_like_page_scan(_document_scan((1800, 1800)), (595, 842))
        )

    def test_bilevel_conversion_caps_resolution_and_preserves_document_marks(self):
        converted = _bilevel_scan_image(_document_scan((2480, 3507)))

        self.assertEqual(converted.mode, "1")
        self.assertEqual(max(converted.size), 2000)
        scale = 2000 / 3507
        self.assertEqual(converted.getpixel((round(100 * scale), round(100 * scale))), 255)
        self.assertEqual(converted.getpixel((round(200 * scale), round(250 * scale))), 0)


class SmartScanPdfTests(unittest.TestCase):
    def test_preprocesses_only_safe_scans_and_preserves_selectable_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scans_pdf = root / "scans.pdf"
            text_pdf = root / "text.pdf"
            source_pdf = root / "source.pdf"
            output_pdf = root / "smart.pdf"

            monochrome = _document_scan(mode="RGB")
            colour = _document_scan(mode="RGB")
            ImageDraw.Draw(colour).rectangle((100, 100, 300, 300), fill=(20, 80, 220))
            monochrome.save(
                scans_pdf,
                "PDF",
                resolution=300,
                save_all=True,
                append_images=[colour],
            )
            _write_text_pdf(text_pdf)
            writer = PdfWriter()
            writer.append(str(scans_pdf))
            writer.append(str(text_pdf))
            writer.write(str(source_pdf))

            replacements = preprocess_smart_scans(source_pdf, output_pdf)

            self.assertEqual(replacements, 1)
            result = PdfReader(str(output_pdf))
            self.assertEqual(len(result.pages), 3)
            self.assertEqual(result.pages[0].images[0].image.mode, "1")
            self.assertEqual(result.pages[1].images[0].image.mode, "RGB")
            self.assertIn("Selectable text", result.pages[2].extract_text())

    def test_leaves_no_output_when_nothing_is_safe_to_convert(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_pdf = root / "colour.pdf"
            output_pdf = root / "smart.pdf"
            colour = Image.new("RGB", (1800, 2400), (40, 90, 180))
            colour.save(source_pdf, "PDF", resolution=300)

            replacements = preprocess_smart_scans(source_pdf, output_pdf)

            self.assertEqual(replacements, 0)
            self.assertFalse(output_pdf.exists())

    def test_skips_image_objects_with_a_soft_mask(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_pdf = root / "masked.pdf"
            output_pdf = root / "smart.pdf"
            _document_scan().save(source_pdf, "PDF", resolution=300)

            reader = PdfReader(str(source_pdf))
            writer = PdfWriter(clone_from=reader)
            image = writer.pages[0].images[0]
            image.indirect_reference.get_object()[NameObject("/SMask")] = NullObject()
            writer.write(str(source_pdf))

            replacements = preprocess_smart_scans(source_pdf, output_pdf)

            self.assertEqual(replacements, 0)
            self.assertFalse(output_pdf.exists())


if __name__ == "__main__":
    unittest.main()
