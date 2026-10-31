import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import httpx

from core.download.checkpoint import ChapterCheckpoint
from core.download.retry import retry_after_seconds, with_retries
from core.book_downloader import BookDownloader


DOC = {"type": "doc", "content": [
    {"type": "paragraph", "content": [{"type": "text", "text": "Text"}]}
]}


def make_chapter(i):
    return SimpleNamespace(id=i, volume="1", number=str(i), index=i,
                           name=f"Chapter {i}", branches=[SimpleNamespace(branch_id=10)])


class ResumeTests(unittest.TestCase):
    def test_checkpoint_reloads_and_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as temp:
            cache = ChapterCheckpoint(temp, 7, 10)
            self.assertIsNone(cache.load(1))
            cache.save(1, {"id": 1, "content": DOC})
            self.assertEqual(cache.load(1)["content"], DOC)
            cache.path(1).write_text("broken JSON", encoding="utf-8")
            self.assertIsNone(cache.load(1))
            with self.assertRaises(ValueError):
                cache.save(1, {"id": 2, "content": DOC})

    def test_resume_downloads_only_missing_chapters(self):
        with tempfile.TemporaryDirectory() as temp:
            cache = ChapterCheckpoint(temp, 7, 10)
            cache.save(1, {"id": 1, "name": "Cached", "content": DOC})
            downloader = BookDownloader(Mock(), Mock())
            downloader.titles.get_title = Mock(return_value=SimpleNamespace(
                id=7, slug_url="7--book", title="Book", authors=(), description=""))
            downloader.chapters.get_chapters = Mock(return_value=[make_chapter(1), make_chapter(2)])
            downloader.contents.get_chapter = Mock(return_value=SimpleNamespace(
                data={"id": 2, "name": "New", "content": DOC}, content=DOC))
            downloader.download("7", Path(temp) / "book.epub", branch_id=10,
                                resume=True, cache_dir=temp, delay=0)
            downloader.contents.get_chapter.assert_called_once_with(
                "7--book", volume="1", number="2", branch_id=10)
            self.assertIsNotNone(cache.load(2))
            chapters = downloader.exporter.export.call_args.kwargs["chapters"]
            self.assertEqual([chapter.title for chapter in chapters], ["Cached", "New"])

    def test_retry_after_and_429(self):
        self.assertEqual(retry_after_seconds("12"), 12)
        self.assertIsNone(retry_after_seconds("invalid"))
        self.assertEqual(
            retry_after_seconds("Wed, 21 Oct 2026 07:28:00 GMT",
                                datetime(2026, 10, 21, 7, 27, tzinfo=timezone.utc)),
            60,
        )
        request = httpx.Request("GET", "https://api.example.test/chapters")
        response = httpx.Response(429, request=request, headers={"Retry-After": "3"})
        call = Mock(side_effect=[httpx.HTTPStatusError(
            "rate limited", request=request, response=response), "ok"])
        waits = []
        self.assertEqual(with_retries(call, attempts=2, sleep=waits.append), "ok")
        self.assertEqual(waits, [3.0])

    def test_retry_does_not_mask_forbidden(self):
        request = httpx.Request("GET", "https://api.example.test")
        response = httpx.Response(403, request=request)
        call = Mock(side_effect=httpx.HTTPStatusError(
            "forbidden", request=request, response=response))
        with self.assertRaises(httpx.HTTPStatusError):
            with_retries(call, attempts=3, sleep=lambda _: None)
        self.assertEqual(call.call_count, 1)


if __name__ == "__main__":
    unittest.main()
