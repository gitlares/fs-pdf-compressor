# SPDX-License-Identifier: AGPL-3.0-or-later
"""Conservative, local preprocessing for high-resolution B&W page scans."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageFilter
from pypdf import PdfReader, PdfWriter


MAX_LONG_EDGE = 2000
MIN_LONG_EDGE = 1600
MIN_PIXEL_COUNT = 1_500_000
BINARIZATION_THRESHOLD = 215
ASPECT_RATIO_TOLERANCE = 0.08
MAX_COLOUR_PIXEL_COUNT = 8
MIN_WHITE_PIXEL_FRACTION = 0.60
MAX_MIDTONE_PIXEL_FRACTION = 0.35
MIN_DARK_PIXEL_FRACTION = 0.0
MAX_DARK_PIXEL_FRACTION = 0.25
LOCAL_BACKGROUND_WINDOW = 3
MIN_COHERENT_FAINT_PIXELS = 2


def _masked_xobject_names(page) -> set[str]:
    """Return direct image XObject names carrying a PDF mask or soft mask.

    Replacing such an image via pypdf can discard its compositing information.
    Read the XObject dictionaries before materialising image data so masked
    images are skipped entirely.
    """
    resources = page.get("/Resources")
    if resources is None:
        return set()
    xobjects = resources.get("/XObject")
    if xobjects is None:
        return set()

    names = set()
    for name, xobject in xobjects.items():
        object_data = xobject.get_object()
        if object_data.get("/Subtype") != "/Image":
            continue
        if "/SMask" not in object_data and "/Mask" not in object_data:
            continue
        names.add(str(name))
    return names


def _has_concentrated_faint_content(luminance: Image.Image) -> bool:
    """Reject spatially coherent marks that thresholding would erase.

    Compare pixels to their local light background, including a one-level
    contrast near white. Connected faint marks are uncertain content, regardless
    of absolute brightness. Isolated speckles are allowed; coherent JPEG ringing
    is deliberately treated as uncertain too, falling back to Balanced.
    """
    background = luminance.filter(ImageFilter.MaxFilter(LOCAL_BACKGROUND_WINDOW))
    contrast = ImageChops.subtract(background, luminance).point(
        lambda value: 255 if value > 0 else 0
    )
    erased = luminance.point(
        lambda value: 255 if value > BINARIZATION_THRESHOLD else 0
    )
    mask = bytearray(ImageChops.darker(contrast, erased).tobytes())
    width, height = luminance.size
    start = mask.find(255)
    while start >= 0:
        pending = [start]
        mask[start] = 0
        count = 1
        while pending:
            position = pending.pop()
            x, y = position % width, position // width
            for ny in range(max(0, y - 1), min(height, y + 2)):
                for nx in range(max(0, x - 1), min(width, x + 2)):
                    neighbour = ny * width + nx
                    if mask[neighbour]:
                        mask[neighbour] = 0
                        count += 1
                        if count >= MIN_COHERENT_FAINT_PIXELS:
                            return True
                        pending.append(neighbour)
        start = mask.find(255, start + 1)
    return False


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
    red, green, blue = sample.split()
    colour_distance = ImageChops.lighter(
        ImageChops.difference(red, green),
        ImageChops.lighter(
            ImageChops.difference(red, blue), ImageChops.difference(green, blue)
        ),
    )
    coloured = sum(colour_distance.histogram()[13:])
    luminance = sample.convert("L")
    histogram = luminance.histogram()
    total = sum(histogram)
    if not total:
        return False
    white = sum(histogram[230:])
    midtone = sum(histogram[64:230])
    dark = sum(histogram[:64])
    if coloured > MAX_COLOUR_PIXEL_COUNT:
        return False
    if _has_concentrated_faint_content(luminance):
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
    """Write a PDF with safe page scans replaced by bilevel images.

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
        masked_names = _masked_xobject_names(page)
        for image_name in page.images.keys():
            # Nested Form XObjects are more complex to inspect safely. Leave
            # them unchanged rather than risk altering a composited image.
            if isinstance(image_name, (list, tuple)) or image_name in masked_names:
                continue
            image_file = page.images[image_name]
            reference = image_file.indirect_reference
            if reference is None:
                continue
            reference_key = (reference.idnum, reference.generation)
            if image_file.image is None:
                continue
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
