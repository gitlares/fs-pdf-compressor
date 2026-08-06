# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""Platform-neutral PDF compression behaviour shared by every desktop UI."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path


APP_NAME = "FS PDF Compressor"
QUALITY_PROFILES = (
    (
        "Preserve quality (minimal loss)",
        "/prepress",
        "Keeps print resolution and quality; the file may shrink only slightly.",
    ),
    (
        "Balanced (recommended)",
        "/ebook",
        "Reduces file size while keeping good on-screen quality.",
    ),
    (
        "Maximum compression",
        "/screen",
        "Creates a smaller file with greater visual quality loss.",
    ),
)
QUALITY_CONTROL_LABELS = ("Preserve", "Balanced", "Maximum")


def _log_path() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / APP_NAME / "compression.log"
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return state_home / "fs-pdf-compressor" / "compression.log"


def compression_logger() -> logging.Logger:
    """Return a local-only error log without sending document data anywhere."""
    logger = logging.getLogger("fs_pdf_compressor")
    if logger.handlers:
        return logger
    try:
        log_path = _log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    except OSError:
        logger.addHandler(logging.NullHandler())
    return logger


def format_file_size(byte_count: int) -> str:
    if byte_count >= 1_000_000:
        return f"{byte_count / 1_000_000:.1f} MB"
    return f"{byte_count / 1_000:.0f} KB"


def compressed_copy_path(original_path: str) -> str:
    path = Path(original_path)
    candidate = path.with_name(f"{path.stem} compressed{path.suffix}")
    sequence = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem} compressed {sequence}{path.suffix}")
        sequence += 1
    return str(candidate)


def bundle_contents_dir() -> Path | None:
    """Return a macOS .app Contents directory when running from one."""
    executable = Path(sys.executable).resolve()
    for parent in executable.parents:
        if parent.name == "Contents":
            return parent
    return None


def _bundled_linux_ghostscript() -> tuple[str | None, dict[str, str]]:
    """Find Ghostscript next to a PyInstaller Linux executable, if present."""
    resource_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    bundled_root = resource_root / "ghostscript"
    bundled_gs = bundled_root / "bin" / "gs"
    environment = os.environ.copy()
    if not bundled_gs.is_file() or not os.access(bundled_gs, os.X_OK):
        return None, environment
    gs_lib = bundled_root / "share" / "ghostscript"
    environment["GS_LIB"] = os.pathsep.join(
        str(path)
        for path in (gs_lib / "Resource" / "Init", gs_lib / "Resource", gs_lib / "lib", gs_lib / "fonts")
        if path.exists()
    )
    library_dir = bundled_root / "lib"
    if library_dir.is_dir():
        existing = environment.get("LD_LIBRARY_PATH", "")
        environment["LD_LIBRARY_PATH"] = os.pathsep.join(
            value for value in (str(library_dir), existing) if value
        )
    return str(bundled_gs), environment


def _snap_ghostscript() -> tuple[str | None, dict[str, str]]:
    """Find Ghostscript and its resources inside a strictly confined Snap."""
    snap_root = os.environ.get("SNAP")
    if not snap_root:
        return None, os.environ.copy()
    root = Path(snap_root)
    executable = root / "usr" / "bin" / "gs"
    resources = sorted((root / "usr" / "share" / "ghostscript").glob("*/Resource"))
    if not executable.is_file() or not resources:
        return None, os.environ.copy()
    resource_root = resources[-1]
    environment = os.environ.copy()
    environment["GS_LIB"] = os.pathsep.join(
        str(path)
        for path in (
            resource_root / "Init",
            resource_root,
            resource_root.parent / "lib",
            resource_root.parent / "fonts",
        )
        if path.exists()
    )
    return str(executable), environment


def get_ghostscript_config() -> tuple[str | None, dict[str, str]]:
    """Locate bundled Ghostscript first, then a development installation."""
    contents_dir = bundle_contents_dir()
    if contents_dir:
        bundled_root = contents_dir / "Resources" / "ghostscript"
        bundled_gs = bundled_root / "bin" / "gs"
        if bundled_gs.is_file() and os.access(bundled_gs, os.X_OK):
            environment = os.environ.copy()
            resource_root = bundled_root / "share" / "ghostscript"
            environment["GS_LIB"] = os.pathsep.join(
                str(path)
                for path in (
                    resource_root / "Resource" / "Init",
                    resource_root / "Resource",
                    resource_root / "lib",
                    resource_root / "fonts",
                )
                if path.exists()
            )
            environment["DYLD_FALLBACK_LIBRARY_PATH"] = str(
                contents_dir / "Frameworks" / "Ghostscript"
            )
            return str(bundled_gs), environment

    bundled_gs, bundled_environment = _bundled_linux_ghostscript()
    if bundled_gs:
        return bundled_gs, bundled_environment

    snap_gs, snap_environment = _snap_ghostscript()
    if snap_gs:
        return snap_gs, snap_environment

    for candidate in (shutil.which("gs"), "/opt/homebrew/bin/gs", "/usr/local/bin/gs"):
        if candidate and os.path.exists(candidate):
            return candidate, os.environ.copy()
    return None, os.environ.copy()


def expand_pdf_paths(paths: list[str]) -> list[str]:
    """Expand files and folders into a stable, de-duplicated list of PDFs."""
    pdfs: list[str] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_file() and path.suffix.lower() == ".pdf":
            pdfs.append(str(path))
        elif path.is_dir():
            pdfs.extend(
                str(candidate)
                for candidate in path.rglob("*")
                if candidate.is_file() and candidate.suffix.lower() == ".pdf"
            )
    return list(dict.fromkeys(pdfs))


def compress_pdf(original_path: str, pdf_settings: str, keep_original: bool):
    """Compress one PDF, preserving the original if no smaller result exists."""
    filename = os.path.basename(original_path)
    logger = compression_logger()
    temp_path = original_path + ".temp.pdf"
    try:
        gs_path, gs_environment = get_ghostscript_config()
        if not gs_path:
            logger.error("Ghostscript was unavailable while compressing %s", filename)
            return f"{filename} — Ghostscript unavailable", None

        original_size = os.path.getsize(original_path)
        result = subprocess.run(
            [
                gs_path,
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                f"-dPDFSETTINGS={pdf_settings}",
                "-dNOPAUSE",
                "-dQUIET",
                "-dBATCH",
                f"-sOutputFile={temp_path}",
                original_path,
            ],
            env=gs_environment,
            capture_output=True,
        )
        if result.returncode != 0 or not os.path.exists(temp_path):
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            logger.error("Ghostscript failed for %s (exit %s): %s", filename, result.returncode, detail)
            return f"{filename} — compression failed", None

        new_size = os.path.getsize(temp_path)
        if new_size >= original_size:
            os.unlink(temp_path)
            return f"{filename} — no size reduction", None

        output_path = compressed_copy_path(original_path) if keep_original else original_path
        os.replace(temp_path, output_path)
        reduction = 100 - (new_size / original_size * 100)
        return (
            f"{os.path.basename(output_path)}   ↓ {reduction:.1f}%",
            {"original_size": original_size, "saved_size": original_size - new_size},
        )
    except Exception:
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass
        logger.exception("Unexpected compression failure for %s", filename)
        return f"{filename} — compression failed", None
