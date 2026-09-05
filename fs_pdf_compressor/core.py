# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""Platform-neutral PDF compression behaviour shared by every desktop UI."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from fs_pdf_compressor.system_trash import TrashError, move_to_system_trash


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


def _bundled_windows_ghostscript() -> tuple[str | None, dict[str, str]]:
    """Find the Ghostscript runtime carried by the Windows PyInstaller bundle."""
    resource_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    bundled_root = resource_root / "ghostscript"
    bundled_gs = bundled_root / "bin" / "gswin64c.exe"
    environment = os.environ.copy()
    if not bundled_gs.is_file():
        return None, environment
    environment["GS_LIB"] = os.pathsep.join(
        str(path)
        for path in (
            bundled_root / "Resource" / "Init",
            bundled_root / "Resource",
            bundled_root / "lib",
        )
        if path.exists()
    )
    environment["PATH"] = os.pathsep.join(
        value for value in (str(bundled_root / "bin"), environment.get("PATH", "")) if value
    )
    return str(bundled_gs), environment


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

    if sys.platform == "win32":
        bundled_gs, bundled_environment = _bundled_windows_ghostscript()
        if bundled_gs:
            return bundled_gs, bundled_environment
        candidates = [shutil.which("gswin64c.exe"), shutil.which("gswin32c.exe")]
        program_files = os.environ.get("ProgramFiles")
        if program_files:
            candidates.extend(
                str(candidate)
                for candidate in sorted(
                    (Path(program_files) / "gs").glob("gs*/bin/gswin64c.exe"),
                    reverse=True,
                )
            )
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate, os.environ.copy()

    for candidate in (shutil.which("gs"), "/opt/homebrew/bin/gs", "/usr/local/bin/gs"):
        if candidate and os.path.exists(candidate):
            return candidate, os.environ.copy()
    return None, os.environ.copy()


def expand_pdf_paths(paths: list[str]) -> list[str]:
    """Expand files and folders into a stable, de-duplicated list of PDFs."""
    pdfs: list[str] = []
    seen: set[str] = set()
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_file() and path.suffix.lower() == ".pdf":
            candidates = (str(path),)
        elif path.is_dir():
            candidates = (
                str(candidate)
                for candidate in path.rglob("*")
                if candidate.is_file() and candidate.suffix.lower() == ".pdf"
            )
        else:
            continue
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                pdfs.append(candidate)
    return pdfs


def _error_output_tail(stream, limit: int = 8192) -> str:
    """Return a bounded diagnostic tail from a process output stream."""
    stream.seek(0, os.SEEK_END)
    stream.seek(max(0, stream.tell() - limit))
    return stream.read().decode("utf-8", errors="replace").strip()


def _ghostscript_command(
    gs_path: str,
    temp_path: str,
    original_path: str,
    pdf_settings: str,
) -> list[str]:
    """Build a pdfwrite command that preserves the document's visible content."""
    return [
        gs_path,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.7",
        "-dPrinted=false",
        "-dWantsOptionalContent=true",
        "-dPreserveMarkedContent=true",
        f"-dPDFSETTINGS={pdf_settings}",
        # /screen and /ebook otherwise force RGB conversion. Ghostscript can
        # lose masked artwork when an RGB image is nested in a CMYK
        # transparency group, so override the preset after it is applied.
        "-sColorConversionStrategy=LeaveColorUnchanged",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        f"-sOutputFile={temp_path}",
        original_path,
    ]


def _original_backup_path(original_path: str) -> str:
    """Choose a visible safety-copy name if moving the original to trash fails."""
    path = Path(original_path)
    candidate = path.with_name(f"{path.stem} original{path.suffix}")
    sequence = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem} original {sequence}{path.suffix}")
        sequence += 1
    return str(candidate)


def _replace_and_trash_original(temp_path: str, original_path: str) -> bool:
    """Install the compressed PDF, retaining the replaced original in system trash.

    The old file first becomes a visible adjacent backup.  This lets us restore
    it if replacing the original path fails, and prevents a failed trash call
    from becoming data loss.
    """
    backup_path = _original_backup_path(original_path)
    os.replace(original_path, backup_path)
    try:
        os.replace(temp_path, original_path)
    except Exception:
        os.replace(backup_path, original_path)
        raise
    try:
        move_to_system_trash(Path(backup_path))
    except TrashError:
        return False
    return True


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
        with tempfile.SpooledTemporaryFile(max_size=64 * 1024, mode="w+b") as error_output:
            result = subprocess.run(
                _ghostscript_command(
                    gs_path,
                    temp_path,
                    original_path,
                    pdf_settings,
                ),
                env=gs_environment,
                stdout=subprocess.DEVNULL,
                stderr=error_output,
            )
            if result.returncode != 0 or not os.path.exists(temp_path):
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                detail = _error_output_tail(error_output)
                logger.error(
                    "Ghostscript failed for %s (exit %s): %s",
                    filename,
                    result.returncode,
                    detail,
                )
                return f"{filename} — compression failed", None

        new_size = os.path.getsize(temp_path)
        if new_size >= original_size:
            os.unlink(temp_path)
            return f"{filename} — no size reduction", None

        if keep_original:
            output_path = compressed_copy_path(original_path)
            os.replace(temp_path, output_path)
            original_trashed = True
        else:
            output_path = original_path
            original_trashed = _replace_and_trash_original(temp_path, original_path)
        reduction = 100 - (new_size / original_size * 100)
        original_note = "" if original_trashed else " (original retained)"
        return (
            f"{os.path.basename(output_path)}   ↓ {reduction:.1f}%{original_note}",
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
