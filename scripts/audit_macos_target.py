#!/usr/bin/env python3
"""Fail a build when any bundled Mach-O requires a newer macOS target."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def version(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def command_output(*args: str) -> str:
    # Python packages can contain resource names outside UTF-8.  `file` may
    # echo one of those names, but that should not make the deployment-target
    # audit itself fail.
    return subprocess.run(
        args,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    ).stdout


def is_macho(path: Path) -> bool:
    return "Mach-O" in command_output("file", "-b", str(path))


def minimum_macos(path: Path) -> str | None:
    output = command_output("xcrun", "vtool", "-show-build", str(path))
    for line in output.splitlines():
        if "minos" in line:
            return line.split("minos", maxsplit=1)[1].strip().split()[0]
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("app", type=Path)
    parser.add_argument("--maximum", required=True)
    arguments = parser.parse_args()
    maximum = version(arguments.maximum)
    failures: list[str] = []
    audited = 0

    for candidate in sorted(arguments.app.joinpath("Contents").rglob("*")):
        if not candidate.is_file() or not is_macho(candidate):
            continue
        minimum = minimum_macos(candidate)
        audited += 1
        if minimum is None:
            failures.append(f"No deployment target found: {candidate}")
        elif version(minimum) > maximum:
            failures.append(f"macOS {minimum}: {candidate}")

    if failures:
        raise SystemExit(
            "Compatibility audit failed (maximum macOS "
            f"{arguments.maximum}):\n" + "\n".join(failures)
        )
    print(f"Compatibility audit passed: {audited} Mach-O files require macOS {arguments.maximum} or earlier.")


if __name__ == "__main__":
    main()
