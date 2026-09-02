# SPDX-License-Identifier: AGPL-3.0-or-later

import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(sys.platform == "darwin", "macOS AppKit test")
class FinderQuickActionTests(unittest.TestCase):
    def test_quick_action_open_urls_starts_only_local_files(self):
        import native_app

        class URL:
            def __init__(self, path, is_file=True):
                self._path = path
                self._is_file = is_file

            def isFileURL(self):
                return self._is_file

            def path(self):
                return self._path

            def scheme(self):
                return None

            def host(self):
                return None

        class Controller:
            def __init__(self):
                self.paths = None
                self.window_was_shown = False

            def show_main_window(self):
                self.window_was_shown = True

            def _start_paths(self, paths):
                self.paths = paths

        delegate = native_app.AppDelegate.alloc().init()
        delegate.controller = Controller()
        delegate.application_openURLs_(
            None,
            [URL("/tmp/one.pdf"), URL("https://example.com/two.pdf", False)],
        )

        self.assertTrue(delegate.controller.window_was_shown)
        self.assertEqual(delegate.controller.paths, ["/tmp/one.pdf"])

    def test_quick_action_internal_url_starts_all_encoded_paths(self):
        import urllib.parse

        import Foundation as FN
        import native_app

        class Controller:
            def __init__(self):
                self.paths = None

            def show_main_window(self):
                pass

            def _start_paths(self, paths):
                self.paths = paths

        delegate = native_app.AppDelegate.alloc().init()
        delegate.controller = Controller()
        with tempfile.TemporaryDirectory() as directory:
            paths = [
                str((Path(directory) / name).resolve())
                for name in ("one.pdf", "two.pdf")
            ]
            bookmarks = []
            for path in paths:
                Path(path).touch()
                file_url = FN.NSURL.fileURLWithPath_(path)
                bookmark, error = file_url.bookmarkDataWithOptions_includingResourceValuesForKeys_relativeToURL_error_(
                    0, None, None, None
                )
                self.assertIsNone(error)
                bookmarks.append(str(bookmark.base64EncodedStringWithOptions_(0)))
            query = urllib.parse.urlencode(
                [("bookmark", value) for value in bookmarks]
            )
            url = FN.NSURL.URLWithString_(
                f"fspdfcompressor://compress?{query}"
            )

            delegate.application_openURLs_(None, [url])

            self.assertEqual(delegate.controller.paths, paths)

    def test_quick_action_internal_url_ignores_untrusted_file_paths(self):
        import Foundation as FN
        import native_app

        class Controller:
            def __init__(self):
                self.paths = None

            def show_main_window(self):
                pass

            def _start_paths(self, paths):
                self.paths = paths

        delegate = native_app.AppDelegate.alloc().init()
        delegate.controller = Controller()
        url = FN.NSURL.URLWithString_(
            "fspdfcompressor://compress?file=%2Ftmp%2Funtrusted.pdf"
        )

        delegate.application_openURLs_(None, [url])

        self.assertEqual(delegate.controller.paths, [])


if __name__ == "__main__":
    unittest.main()
