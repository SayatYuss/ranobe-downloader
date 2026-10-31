"""Core dependency injection tests; no network, CLI, keyring, or TTY."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from core.book_downloader import BookDownloader
from core.chapter_content import ChapterContent
from exporters.epub import EpubExporter
from zipfile import ZipFile


class DownloaderCoreTests(unittest.TestCase):
    def setUp(self):
        self.title = SimpleNamespace(
            id=7, slug_url="7--test", title="Test book",
            authors=("Author",), description="", cover_url=None,
        )
        self.item = SimpleNamespace(
            id=11, volume="1", number="1", name="First",
            index=1, branches=[],
        )
        self.titles = Mock()
        self.titles.get_title.return_value = self.title
        self.chapters = Mock()
        self.chapters.get_chapters.return_value = [self.item]
        self.contents = Mock()
        self.contents.get_chapter.return_value = ChapterContent.from_api({
            "id": 11, "volume": "1", "number": "1",
            "name": "First", "content": "<p>Text</p>",
        })

    def test_injected_sources_prepare_and_generate_real_epub(self):
        downloader = BookDownloader(
            titles=self.titles, chapters=self.chapters,
            contents=self.contents, exporter=EpubExporter(),
        )
        plan = downloader.prepare("7--test")
        self.assertEqual(plan.title.title, "Test book")
        with tempfile.TemporaryDirectory() as tmp:
            path = downloader.download(plan, Path(tmp) / "book.epub",
                                       cache_dir=Path(tmp) / "cache", delay=0)
            with ZipFile(path) as epub:
                self.assertIsNone(epub.testzip())
                self.assertIn(b"Text", epub.read("OEBPS/chapter-0001.xhtml"))
        self.titles.get_title.assert_called_once_with("7--test")
        self.chapters.get_chapters.assert_called_once_with("7--test")
        self.contents.get_chapter.assert_called_once_with(
            "7--test", volume="1", number="1", branch_id=None,
        )

    def test_requires_client_or_complete_sources(self):
        with self.assertRaisesRegex(ValueError, "client or all three"):
            BookDownloader()
        with self.assertRaisesRegex(ValueError, "client or all three"):
            BookDownloader(titles=self.titles, chapters=self.chapters)

    def test_custom_exporter_without_client(self):
        exporter = Mock()
        exporter.export.return_value = Path("book.epub")
        downloader = BookDownloader(
            titles=self.titles, chapters=self.chapters,
            contents=self.contents, exporter=exporter,
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = downloader.download("7--test", Path(tmp) / "book.epub",
                                         cache_dir=tmp, delay=0)
            self.assertEqual(result, Path("book.epub"))
        exporter.export.assert_called_once()


if __name__ == "__main__":
    unittest.main()
