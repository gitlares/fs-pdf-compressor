# SPDX-License-Identifier: AGPL-3.0-or-later

from io import BytesIO
from unittest.mock import patch
import unittest

from PIL import ImageCms
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject

from fs_pdf_compressor.pdf_validation import (
    has_invalid_icc,
    identify_missing_profile,
    restore_missing_profile,
    same_page_geometry,
)


def document(profile_data=None, *, components=3, width=500, extra_space=None):
    writer = PdfWriter()
    page = writer.add_blank_page(width=width, height=400)
    spaces = DictionaryObject()
    if profile_data is not None:
        profile = DecodedStreamObject()
        profile.set_data(profile_data)
        profile[NameObject("/N")] = NumberObject(components)
        spaces[NameObject("/Custom")] = ArrayObject([
            NameObject("/ICCBased"), writer._add_object(profile)
        ])
    if extra_space:
        spaces[NameObject("/Other")] = NameObject(extra_space)
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/ColorSpace"): spaces})
    buffer = BytesIO()
    writer.write(buffer)
    return PdfReader(buffer)


class PdfFidelityTests(unittest.TestCase):
    def test_valid_embedded_rgb_profile_does_not_need_a_known_profile_name(self):
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        reader = document(profile)
        self.assertFalse(has_invalid_icc(reader))

    def test_rejects_empty_truncated_and_mismatched_profiles(self):
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        for data, components in [(b"", 3), (profile[:132], 3), (profile, 4)]:
            with self.subTest(length=len(data), components=components):
                reader = document(data, components=components)
                self.assertTrue(has_invalid_icc(reader))

    def test_checks_document_dimensions(self):
        self.assertTrue(same_page_geometry(document(), document()))
        self.assertFalse(same_page_geometry(document(), document(width=510)))

    def test_ambiguous_or_unmatched_profile_is_not_restored(self):
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        source, output = document(profile), document(b"")
        self.assertIsNone(identify_missing_profile(source, output))
        with patch(
            "fs_pdf_compressor.pdf_validation._jpeg_profile_evidence",
            side_effect=[{}, {}],
        ):
            self.assertIsNone(identify_missing_profile(source, output))

    def test_restores_original_profile_bytes(self):
        data = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        source, output = document(data), document(b"")
        profile = source.pages[0]["/Resources"]["/ColorSpace"]["/Custom"][1].get_object()
        empty = output.pages[0]["/Resources"]["/ColorSpace"]["/Custom"][1].get_object()
        key = (400, 300, b"same-image")
        with patch(
            "fs_pdf_compressor.pdf_validation._jpeg_profile_evidence",
            side_effect=[{key: [profile]}, {key: [empty]}],
        ):
            matched = identify_missing_profile(source, output)
        self.assertIs(matched, profile)
        repaired = BytesIO()
        self.assertTrue(restore_missing_profile(output, repaired, source, matched))
        checked = PdfReader(repaired)
        self.assertFalse(has_invalid_icc(checked))
        space = checked.pages[0]["/Resources"]["/ColorSpace"]["/Custom"]
        self.assertEqual(space[1].get_object().get_data(), data)
