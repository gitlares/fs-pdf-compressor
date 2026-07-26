# SPDX-License-Identifier: AGPL-3.0-or-later

import unittest

from fs_pdf_compressor.batch import BatchSummary, completion_text


class BatchSummaryTests(unittest.TestCase):
    def test_empty_batch_has_no_summary(self):
        self.assertIsNone(BatchSummary.from_metrics([None, None]))
        self.assertEqual(
            completion_text([None, None]),
            "Done — no files were reduced",
        )

    def test_summary_matches_the_existing_product_copy(self):
        metrics = [
            {"original_size": 1_000_000, "saved_size": 500_000},
            {"original_size": 2_000_000, "saved_size": 500_000},
        ]

        summary = BatchSummary.from_metrics(metrics)

        self.assertIsNotNone(summary)
        self.assertEqual(summary.completed_files, 2)
        self.assertAlmostEqual(summary.average_reduction, 37.5)
        self.assertEqual(summary.saved_size, 1_000_000)
        self.assertEqual(
            summary.status_text,
            "Done — 37.5% average · 1.0 MB saved",
        )
        self.assertEqual(summary.compact_text, "38% smaller")


if __name__ == "__main__":
    unittest.main()
