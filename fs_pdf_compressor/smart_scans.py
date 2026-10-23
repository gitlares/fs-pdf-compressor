# SPDX-License-Identifier: AGPL-3.0-or-later
"""Conservative, local preprocessing for high-resolution B&W page scans."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from pypdf import PdfReader, PdfWriter


MAX_LONG_EDGE = 2000
MIN_LONG_EDGE = 1600
MIN_PIXEL_COUNT = 1_500_000
BINARIZATION_THRESHOLD = 215
ASPECT_RATIO_TOLERANCE = 0.08
MAX_COLOUR_PIXEL_FRACTION = 0.0005
MIN_WHITE_PIXEL_FRACTION = 0.60
MAX_MIDTONE_PIXEL_FRACTION = 0.35
MIN_DARK_PIXEL_FRACTION = 0.0
MAX_DARK_PIXEL_FRACTION = 0.25


def _looks_like_page_scan(
    image: Image.Image,
    page_size: tuple[float, float],
) -> bool:
    """Return whether an image is a safe candidate for B&W page encoding.

    The classifier deliberately rejects uncertain content. A candidate must be
    large, match the page aspect ratio, contain virtually no chromatic pixels,
    and have the tonal distribution of a light document rather than a photo.
    """
    width, height = image.size
    if max(width, height) < MIN_LONG_EDGE or width * height < MIN_PIXEL_COUNT:
        return False

    page_width, page_height = page_size
    if min(page_width, page_height) <= 0:
        return False
    image_ratio = max(width, height) / min(width, height)
    page_ratio = max(page_width, page_height) / min(page_width, page_height)
    if abs(image_ratio - page_ratio) / page_ratio > ASPECT_RATIO_TOLERANCE:
        return False

    sample = image.convert("RGB")
    sample.thumbnail((512, 512), Image.Resampling.LANCZOS)
    pixels = list(sample.getdata())
    if not pixels:
        return False

    coloured = 0
    white = 0
    midtone = 0
    dark = 0
    for red, green, blue in pixels:
        if max(red, green, blue) - min(red, green, blue) > 12:
            coloured += 1
        luminance = (299 * red + 587 * green + 114 * blue) // 1000
        if luminance >= 230:
            white += 1
        elif luminance >= 64:
            midtone += 1
        else:
            dark += 1

    total = len(pixels)
    if coloured > max(8, round(total * MAX_COLOUR_PIXEL_FRACTION)):
        return False
    white_fraction = white / total
    midtone_fraction = midtone / total
    dark_fraction = dark / total
    return (
        white_fraction >= MIN_WHITE_PIXEL_FRACTION
        and midtone_fraction <= MAX_MIDTONE_PIXEL_FRACTION
        and MIN_DARK_PIXEL_FRACTION <= dark_fraction <= MAX_DARK_PIXEL_FRACTION
    )


def _bilevel_scan_image(image: Image.Image) -> Image.Image:
    """Create a sharp, bounded-resolution 1-bit copy of a document scan."""
    grayscale = image.convert("L")
    if max(grayscale.size) > MAX_LONG_EDGE:
        scale = MAX_LONG_EDGE / max(grayscale.size)
        target_size = tuple(max(1, round(value * scale)) for value in grayscale.size)
        grayscale = grayscale.resize(target_size, Image.Resampling.LANCZOS)
    return grayscale.point(
        lambda value: 255 if value > BINARIZATION_THRESHOLD else 0,
        mode="1",
    )


def preprocess_smart_scans(source: str | Path, destination: str | Path) -> int:
    """Write a PDF with safe page scans replaced by lossless bilevel images.

    Returns the number of distinct image objects replaced. No destination is
    left behind when there are no safe candidates. Parsing and writing errors
    intentionally propagate so the caller can fall back to its normal path.
    """
    source_path = Path(source)
    destination_path = Path(destination)
    destination_path.unlink(missing_ok=True)

    reader = PdfReader(str(source_path), strict=False)
    writer = PdfWriter(clone_from=reader)
    replaced_references: set[tuple[int, int]] = set()
    replacements = 0

    for page in writer.pages:
        page_size = (float(page.mediabox.width), float(page.mediabox.height))
        for image_file in page.images:
            reference = image_file.indirect_reference
            if reference is None or image_file.image is None:
                continue
            reference_key = (reference.idnum, reference.generation)
            if reference_key in replaced_references:
                continue
            if not _looks_like_page_scan(image_file.image, page_size):
                continue
            image_file.replace(_bilevel_scan_image(image_file.image), resolution=300)
            replaced_references.add(reference_key)
            replacements += 1

    if replacements == 0:
        return 0
    try:
        with destination_path.open("xb") as output:
            writer.write(output)
    except Exception:
        destination_path.unlink(missing_ok=True)
        raise
    return replacements
