"""Public exception mapping and validation regression tests."""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import httpx

from core.download.plan import DownloadPlan
from ranobe_downloader import Downloader, AuthenticationError, NetworkError, ProviderError


class LibraryErrorsTests(unittest.TestCase):
    def setUp(self):
        self.backend = Mock()
        self.backend.exporter = object()
        self.backend.prepare.return_value = DownloadPlan(
            SimpleNamespace(id=1, title="Demo", slug_url="1--demo", authors=()),
            (object(),), (),
        )
        self.backend.download.return_value = Path("book.epub")
        self.api = Downloader(backend=self.backend)

    def tearDown(self):
        self.api.close()

    def test_invalid_inputs_do_not_reach_backend(self):
        for options in ({"delay": float("nan")}, {"limit": 0}, {"retries": 0},
                        {"image_quality": 101}, {"image_max_width": 0}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.api.download("1--demo", **options)
        self.backend.prepare.assert_not_called()
        with self.assertRaisesRegex(ValueError, "reference"):
            self.api.get_book("  ")

    def test_access_denied_has_typed_exception(self):
        request = httpx.Request("GET", "https://example.com/book")
        response = httpx.Response(403, request=request)
        self.backend.prepare.side_effect = httpx.HTTPStatusError(
            "Forbidden", request=request, response=response)
        with self.assertRaises(AuthenticationError) as context:
            self.api.get_book("1--demo")
        self.assertIsInstance(context.exception.__cause__, httpx.HTTPStatusError)

    def test_provider_failure_on_download_restores_exporter(self):
        request = httpx.Request("GET", "https://example.com/chapter")
        response = httpx.Response(500, request=request)
        self.backend.download.side_effect = httpx.HTTPStatusError(
            "error", request=request, response=response)
        original = self.backend.exporter
        with self.assertRaises(ProviderError):
            self.api.download("1--demo")
        self.assertIs(self.backend.exporter, original)

    def test_network_exception(self):
        request = httpx.Request("GET", "https://example.com/book")
        self.backend.prepare.side_effect = httpx.ConnectError("offline", request=request)
        with self.assertRaises(NetworkError):
            self.api.get_book("1--demo")


if __name__ == "__main__":
    unittest.main()
