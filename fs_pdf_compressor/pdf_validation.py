# SPDX-License-Identifier: AGPL-3.0-or-later
"""Check document geometry and embedded colour profiles before accepting output."""

from hashlib import sha256

from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject, StreamObject


def _objects(root):
    pending = [root]
    visited = set()
    while pending:
        obj = pending.pop()
        if isinstance(obj, IndirectObject):
            key = (obj.idnum, obj.generation)
            if key in visited:
                continue
            visited.add(key)
            obj = obj.get_object()
        yield obj
        if isinstance(obj, DictionaryObject):
            pending.extend(obj.values())
        elif isinstance(obj, ArrayObject):
            pending.extend(obj)


def _valid_profile(profile):
    if not isinstance(profile, StreamObject):
        return False
    data = profile.get_data()
    if len(data) < 132 or data[36:40] != b"acsp":
        return False
    size = int.from_bytes(data[:4], "big")
    if not 132 <= size <= len(data):
        return False
    channels = {b"GRAY": 1, b"RGB ": 3, b"CMYK": 4}.get(data[16:20])
    return channels is not None and channels == profile.get("/N")


def has_invalid_icc(reader):
    checked = set()
    for obj in _objects(reader.root_object):
        if isinstance(obj, ArrayObject) and obj and obj[0] == "/ICCBased":
            if len(obj) != 2:
                return True
            profile = obj[1].get_object()
            identity = id(profile)
            if identity not in checked:
                if not _valid_profile(profile):
                    return True
                checked.add(identity)
    return False


def _icc_spaces(document):
    for obj in _objects(document.root_object):
        if isinstance(obj, ArrayObject) and len(obj) == 2 and obj[0] == "/ICCBased":
            yield obj


def _jpeg_profile_evidence(document):
    """Use unchanged JPEG bytes and dimensions as evidence of profile identity."""
    evidence = {}
    for obj in _objects(document.root_object):
        if not isinstance(obj, StreamObject) or obj.get("/Subtype") != "/Image":
            continue
        if obj.get("/Filter") != "/DCTDecode":
            continue
        space = obj.get("/ColorSpace")
        if space is None:
            continue
        space = space.get_object()
        if isinstance(space, ArrayObject) and len(space) == 2 and space[0] == "/ICCBased":
            key = (obj.get("/Width"), obj.get("/Height"), sha256(obj.get_data()).digest())
            evidence.setdefault(key, []).append(space[1].get_object())
    return evidence


def identify_missing_profile(source, broken):
    """Resolve a single empty profile using surviving profiles and unchanged images."""
    source_profiles = [space[1].get_object() for space in _icc_spaces(source)]
    broken_profiles = [space[1].get_object() for space in _icc_spaces(broken)]
    missing = {id(profile): profile for profile in broken_profiles if not _valid_profile(profile)}
    if len(missing) != 1:
        return None
    empty = next(iter(missing.values()))
    if not isinstance(empty, StreamObject) or empty.get_data():
        return None

    surviving = {profile.get_data() for profile in broken_profiles if _valid_profile(profile)}
    candidates = {
        profile.get_data(): profile for profile in source_profiles
        if _valid_profile(profile) and profile.get("/N") == empty.get("/N")
        and profile.get_data() not in surviving
    }
    if len(candidates) != 1:
        return None
    data, profile = next(iter(candidates.items()))
    original_evidence = _jpeg_profile_evidence(source)
    output_evidence = _jpeg_profile_evidence(broken)
    matched = {
        original.get_data()
        for key, profiles in output_evidence.items() if any(item is empty for item in profiles)
        for original in original_evidence.get(key, [])
    }
    if matched != {data}:
        return None
    return profile


def restore_missing_profile(input_path, output_path, source, source_profile):
    writer = PdfWriter(clone_from=input_path)
    empty_profiles = {
        id(profile): profile for space in _icc_spaces(writer)
        for profile in [space[1].get_object()] if not _valid_profile(profile)
    }
    if len(empty_profiles) != 1:
        return False
    empty = next(iter(empty_profiles.values()))
    if not isinstance(empty, StreamObject) or empty.get_data():
        return False
    if empty.get("/N") != source_profile.get("/N"):
        return False

    surviving_profiles = {
        item[1].get_object().get_data() for item in _icc_spaces(writer)
        if _valid_profile(item[1].get_object())
    }
    missing_source_profiles = {
        item[1].get_object().get_data() for item in _icc_spaces(source)
        if _valid_profile(item[1].get_object())
        and item[1].get_object().get("/N") == empty.get("/N")
    } - surviving_profiles
    if missing_source_profiles != {source_profile.get_data()}:
        return False

    replacement = source_profile.clone(writer).indirect_reference
    for space in _icc_spaces(writer):
        if space[1].get_object() is empty:
            space[1] = replacement
    if has_invalid_icc(writer):
        return False
    writer.write(output_path)
    return True


def _page_geometry(reader):
    return [
        (tuple(page.mediabox), tuple(page.cropbox), page.rotation, page.user_unit)
        for page in reader.pages
    ]


def same_page_geometry(source, output):
    return _page_geometry(source) == _page_geometry(output)


def same_page_text(source, output):
    """Ignore wrapping and spacing changes, but detect lost or altered text."""
    return all(
        "".join(before.extract_text().split()) == "".join(after.extract_text().split())
        for before, after in zip(source.pages, output.pages, strict=True)
    )
