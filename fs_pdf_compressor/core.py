# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""Platform-neutral PDF compression behaviour shared by every desktop UI."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from fs_pdf_compressor.system_trash import TrashError, move_to_system_trash
from fs_pdf_compressor.file_guard import FileBusyError, document_lock


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
                canonical = str(Path(candidate).resolve())
                if canonical not in seen:
                    seen.add(canonical)
                    pdfs.append(candidate)
    return pdfs


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


def _ghostscript_subprocess_options() -> dict[str, int]:
    """Keep Ghostscript's Windows console invisible during compression."""
    if os.name == "nt":
        # CREATE_NO_WINDOW is the Windows console-free launch flag.  Keeping
        # its value local avoids a Windows-only subprocess constant on macOS
        # and Linux.
        return {"creationflags": 0x08000000}
    return {}


def _replace_and_trash_original(temp_path: str, original_path: str) -> bool:
    """Try recycling before replacement; restore if installing output fails.

    The temporary recovery snapshot is not a third output mode. It protects
    against a trash implementation that moves a file and then reports failure.
    """
    fd, backup_path = tempfile.mkstemp(prefix=".fs-pdf-recovery-", suffix=".tmp", dir=Path(original_path).parent)
    try:
        before = os.stat(original_path)
        with os.fdopen(fd, "wb") as backup, open(original_path, "rb") as source:
            shutil.copyfileobj(source, backup, length=1024 * 1024)
            backup.flush()
            os.fsync(backup.fileno())
        shutil.copystat(original_path, backup_path)
        after = os.stat(original_path)
        if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
            raise OSError("Original PDF changed while preparing replacement")
        try:
            move_to_system_trash(Path(original_path))
            if os.path.exists(original_path):
                raise TrashError("The original was not moved to the system trash")
        except Exception:
            # Recycling is best-effort protection, not a prerequisite for the
            # user's selected replace mode. Keep the recovery snapshot until
            # installation succeeds, including when the trash backend moved
            # the original before reporting an error.
            pass
        try:
            os.replace(temp_path, original_path)
        except Exception:
            if not os.path.exists(original_path):
                os.replace(backup_path, original_path)
            raise
        return True
    finally:
        # If restoration itself failed, retain the recovery file for recovery.
        if os.path.exists(original_path):
            Path(backup_path).unlink(missing_ok=True)


def compress_pdf(original_path: str, pdf_settings: str, keep_original: bool):
    """Compress one PDF, preserving the original if no smaller result exists."""
    original_path = str(Path(original_path).resolve())
    try:
        with document_lock(original_path):
            return _compress_locked(original_path, pdf_settings, keep_original)
    except FileBusyError:
        return f"{Path(original_path).name} — already being compressed", None
    except OSError:
        return f"{Path(original_path).name} — could not open PDF", None


def _valid_pdf_output(path):
    """Reject empty/truncated output; this is not a visual fidelity check."""
    with open(path, "rb") as output:
        if not output.read(8).startswith(b"%PDF-"):
            return False
        output.seek(0, os.SEEK_END)
        size = output.tell()
        output.seek(max(0, size - 1024))
        return b"%%EOF" in output.read()


def _compress_locked(original_path, pdf_settings, keep_original):
    filename = os.path.basename(original_path)
    temp_path = None
    try:
        gs_path, gs_environment = get_ghostscript_config()
        if not gs_path:
            return f"{filename} — Ghostscript unavailable", None

        original_stat = os.stat(original_path)
        original_size = original_stat.st_size
        fd, temp_path = tempfile.mkstemp(prefix=".fs-pdf-", suffix=".tmp", dir=Path(original_path).parent)
        os.close(fd)
        result = subprocess.run(
            _ghostscript_command(
                gs_path,
                temp_path,
                original_path,
                pdf_settings,
            ),
            env=gs_environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **_ghostscript_subprocess_options(),
        )
        if result.returncode != 0 or not os.path.exists(temp_path):
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            return f"{filename} — compression failed", None

        new_size = os.path.getsize(temp_path)
        if not _valid_pdf_output(temp_path):
            raise ValueError("Ghostscript produced an invalid or truncated PDF")
        if new_size >= original_size:
            os.unlink(temp_path)
            return f"{filename} — no size reduction", None

        current_stat = os.stat(original_path)
        if (original_stat.st_ino, original_stat.st_size, original_stat.st_mtime_ns) != (current_stat.st_ino, current_stat.st_size, current_stat.st_mtime_ns):
            raise OSError("Original PDF changed during compression")
        shutil.copystat(original_path, temp_path)
        if keep_original:
            output_path = compressed_copy_path(original_path)
            output = open(output_path, "xb")
            try:
                with output, open(temp_path, "rb") as source:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
            except Exception:
                Path(output_path).unlink(missing_ok=True)
                raise
            shutil.copystat(original_path, output_path)
            os.unlink(temp_path)
        else:
            output_path = original_path
            _replace_and_trash_original(temp_path, original_path)
        reduction = 100 - (new_size / original_size * 100)
        return (
            f"{os.path.basename(output_path)}   ↓ {reduction:.1f}%",
            {"original_size": original_size, "saved_size": original_size - new_size},
        )
    except Exception as error:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass
        if isinstance(error, TrashError):
            return f"{filename} — could not recycle original; not replaced", None
        return f"{filename} — compression failed", None
