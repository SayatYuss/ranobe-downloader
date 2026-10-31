"""Public Python API tests; no network or credential storage."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from core.download.plan import DownloadPlan, Translation
from ranobe_downloader import Book, Downloader


class LibraryApiTests(unittest.TestCase):
    def setUp(self):
        self.backend = Mock()
        self.backend.exporter = object()
        self.plan = DownloadPlan(
            title=SimpleNamespace(id=42, title="Demo", slug_url="42--demo",
                                  authors=("Author",)),
            chapters=(object(), object()),
            translations=(Translation(7, 2, "Team"),),
        )
        self.backend.prepare.return_value = self.plan
        self.backend.download.return_value = Path("demo.txt")

    def test_prepare_metadata_and_export_format(self):
        with Downloader(backend=self.backend) as api:
            book = api.get_book("42--demo")
            self.assertIsInstance(book, Book)
            self.assertEqual(book.title, "Demo")
            self.assertEqual(book.chapter_count, 2)
            self.assertEqual(book.translations[0].branch_id, 7)
            original = self.backend.exporter
            result = api.download(book, format="txt", output="demo.txt",
                                  branch_id=7, delay=0)
            self.assertEqual(result, Path("demo.txt"))
            self.assertEqual(type(self.backend.download.call_args.kwargs["branch_id"]), int)
            self.assertEqual(self.backend.download.call_args.args[0], self.plan)
            self.assertIs(self.backend.exporter, original)

    def test_exporter_restored_on_failure(self):
        self.backend.download.side_effect = ValueError("test")
        with Downloader(backend=self.backend) as api:
            book = api.get_book("42--demo")
            previous = self.backend.exporter
            with self.assertRaisesRegex(ValueError, "test"):
                api.download(book, format="html")
            self.assertIs(self.backend.exporter, previous)

    def test_closed_downloader_is_rejected(self):
        api = Downloader(backend=self.backend)
        api.close()
        api.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            api.get_book("42--demo")

    def test_invalid_format_without_network(self):
        with Downloader(backend=self.backend) as api:
            with self.assertRaisesRegex(ValueError, "format"):
                api.download("42--demo", format="pdf")

    def test_default_path_and_progress_forwarding(self):
        with Downloader(backend=self.backend) as api:
            cb = Mock()
            api.download("42--demo", format="epub", branch_id=7, progress=cb)
            self.assertEqual(self.backend.download.call_args.args[1],
                             Path("output/42--demo_7.epub"))
            self.assertIs(self.backend.download.call_args.kwargs["progress"], cb)


if __name__ == "__main__":
    unittest.main()
