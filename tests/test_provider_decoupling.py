"""Provider/media injection smoke tests without RanobeLib client."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from core.book_downloader import BookDownloader
from core.chapter_content import ChapterContent
from core.download.processor import ContentProcessor


class ProviderDecouplingTests(unittest.TestCase):
    def test_custom_media_is_used(self):
        media = Mock()
        media.resolve_html_images.return_value = ({"image-src": "pic"}, ["pic"])
        media.load_images.return_value = {"pic": ("images/pic.png", b"\x89PNG\r\n\x1a\n", "image/png")}
        item = SimpleNamespace(id=9, volume="1", number="1", name="Chapter")
        data = {"id": 9, "name": "Chapter", "content": '<p>Text</p><img src="image-src">'}
        chapter = ContentProcessor(media=media).process(data, item, Path("cache"))
        self.assertIn('src="images/pic.png"', chapter.xhtml)
        media.resolve_html_images.assert_called_once()
        media.load_images.assert_called_once()

    def test_custom_cover_provider_reaches_exporter(self):
        titles, chapters, contents, exporter = Mock(), Mock(), Mock(), Mock()
        titles.get_title.return_value = SimpleNamespace(
            id=1, slug_url="1--book", title="Book", authors=(), description="",
            cover_url="https://example.com/cover.png")
        chapters.get_chapters.return_value = [
            SimpleNamespace(id=7, volume="1", number="1", index=1, name="Chapter", branches=[])
        ]
        contents.get_chapter.return_value = ChapterContent.from_api({
            "id": 7, "volume": "1", "number": "1", "name": "Chapter",
            "content": "<p>Text</p>",
        })
        exporter.export.return_value = Path("test.epub")
        cover = Mock(return_value=(b"pngdata", "image/png"))
        downloader = BookDownloader(
            titles=titles, chapters=chapters, contents=contents,
            exporter=exporter, cover_downloader=cover,
        )
        with tempfile.TemporaryDirectory() as tmp:
            downloader.download("1--book", Path(tmp) / "test.epub", cache_dir=tmp, delay=0)
        cover.assert_called_once_with("https://example.com/cover.png")
        self.assertEqual(exporter.export.call_args.kwargs["cover"], b"pngdata")


if __name__ == "__main__":
    unittest.main()
