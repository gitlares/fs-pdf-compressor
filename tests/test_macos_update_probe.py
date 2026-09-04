# SPDX-License-Identifier: AGPL-3.0-or-later

import unittest
from unittest import mock

from fs_pdf_compressor.macos_update_probe import (
    appcast_may_offer_update,
    probe_for_update,
)


def _appcast(*versions: str) -> bytes:
    items = "".join(
        f"""
        <item>
          <sparkle:version>{version}</sparkle:version>
          <enclosure url="https://example.com/{version}.zip" />
        </item>
        """
        for version in versions
    )
    return f"""
    <rss xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle">
      <channel>{items}</channel>
    </rss>
    """.encode()


class AppcastProbeTests(unittest.TestCase):
    def test_detects_newer_numeric_version(self):
        self.assertTrue(appcast_may_offer_update(_appcast("1.0.13"), "1.0.12"))

    def test_ignores_current_and_older_versions(self):
        self.assertFalse(
            appcast_may_offer_update(_appcast("1.0.12", "1.0.11"), "1.0.12")
        )

    def test_treats_unrecognized_version_as_a_reason_to_load_sparkle(self):
        self.assertTrue(appcast_may_offer_update(_appcast("next-release"), "1.0.12"))

    def test_rejects_non_https_feed_without_network_access(self):
        self.assertIsNone(probe_for_update("http://example.com/appcast.xml", "1.0.12"))

    def test_invalid_feed_is_not_treated_as_an_update(self):
        with mock.patch(
            "fs_pdf_compressor.macos_update_probe.urlopen", side_effect=OSError
        ):
            self.assertIsNone(
                probe_for_update("https://example.invalid/appcast.xml", "1.0.12")
            )
