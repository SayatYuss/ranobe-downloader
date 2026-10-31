"""Offline contract tests for individual pipeline stages."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.chapter_content import ChapterContent, ChapterContentUnavailable
from core.download.checkpoint import ChapterCheckpoint
from core.download.fetcher import ChapterFetcher
from core.download.processor import ContentProcessor


def item():
    return SimpleNamespace(id=42, volume="1", number="2", name="Second")


class PipelineTests(unittest.TestCase):
    def test_fetcher_saves_and_reuses_checkpoint(self):
        source = Mock()
        source.get_chapter.return_value = ChapterContent.from_api({
            "id": 42, "volume": "1", "number": "2", "content": "<p>Hello</p>",
        })
        with tempfile.TemporaryDirectory() as tmp:
            fetcher = ChapterFetcher(source, ChapterCheckpoint(tmp, 7, None))
            data, cached = fetcher.fetch("7--book", item(), resume=True)
            self.assertFalse(cached)
            same, cached = fetcher.fetch("7--book", item(), resume=True)
            self.assertTrue(cached)
            self.assertEqual(data, same)
            source.get_chapter.assert_called_once()

    def test_fetcher_paid_content_is_not_cached(self):
        source = Mock()
        source.get_chapter.return_value = ChapterContent.from_api({
            "id": 42, "volume": "1", "number": "2",
            "restricted_view": {"is_open": False, "price": 10},
        })
        with tempfile.TemporaryDirectory() as tmp:
            store = ChapterCheckpoint(tmp, 7, None)
            fetcher = ChapterFetcher(source, store)
            with self.assertRaisesRegex(ChapterContentUnavailable, "paid_content"):
                fetcher.fetch("7--book", item())
            self.assertFalse(store.path(42).exists())

    def test_processor_html_and_structured_content(self):
        processor = ContentProcessor()
        with tempfile.TemporaryDirectory() as tmp:
            for content in ("<p>Hello</p>", {"type": "doc", "content": [
                {"type": "paragraph", "content": [
                    {"type": "text", "text": "Hello"}]}]}):
                result = processor.process(
                    {"id": 42, "name": "Second", "content": content},
                    item(), Path(tmp),
                )
                self.assertEqual(result.title, "Second")
                self.assertIn("Hello", result.xhtml)
                self.assertEqual(result.images, ())

    def test_processor_rejects_missing_content(self):
        with self.assertRaisesRegex(ChapterContentUnavailable, "missing_content"):
            ContentProcessor().process({"id": 42}, item(), "cache")


if __name__ == "__main__":
    unittest.main()
