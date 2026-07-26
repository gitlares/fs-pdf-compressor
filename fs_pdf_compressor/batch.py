# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""Small, platform-neutral helpers for presenting compression batches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from fs_pdf_compressor.core import format_file_size


CompressionMetric = Mapping[str, int]


@dataclass(frozen=True)
class BatchSummary:
    """Aggregate the successful results from one compression batch."""

    completed_files: int
    average_reduction: float
    saved_size: int

    @classmethod
    def from_metrics(
        cls, metrics: Iterable[CompressionMetric | None]
    ) -> BatchSummary | None:
        completed = [metric for metric in metrics if metric is not None]
        if not completed:
            return None
        average = sum(
            metric["saved_size"] / metric["original_size"] * 100 for metric in completed
        ) / len(completed)
        return cls(
            completed_files=len(completed),
            average_reduction=average,
            saved_size=sum(metric["saved_size"] for metric in completed),
        )

    @property
    def status_text(self) -> str:
        return (
            f"Done — {self.average_reduction:.1f}% average · "
            f"{format_file_size(self.saved_size)} saved"
        )

    @property
    def compact_text(self) -> str:
        return f"{self.average_reduction:.0f}% smaller"


def completion_text(metrics: Iterable[CompressionMetric | None]) -> str:
    summary = BatchSummary.from_metrics(metrics)
    return summary.status_text if summary else "Done — no files were reduced"
