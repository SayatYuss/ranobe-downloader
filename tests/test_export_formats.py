"""Cross-format export tests with real files and no network."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from core.book_downloader import BookDownloader
from core.chapter_content import ChapterContent
from core.download.models import NormalizedChapter
from exporters.epub import EpubChapter, EpubExporter
from exporters.text import HtmlExporter, TxtExporter


class ExportFormatsTests(unittest.TestCase):
    def test_epub_alias_keeps_old_api(self):
        self.assertIs(EpubChapter, NormalizedChapter)

    def test_txt_and_html_from_same_normalized_chapter(self):
        chapter = NormalizedChapter(
            "Глава 1",
            '<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml">'
            '<body><h1>Глава 1</h1><p>Привет &amp; мир</p>'
            '<img src="images/a.gif" alt="" /></body></html>',
            images=(("images/a.gif", b"GIF89a123", "image/gif"),),
        )
        with tempfile.TemporaryDirectory() as tmp:
            text_path = TxtExporter().export(Path(tmp) / "book.txt", title="Книга", chapters=[chapter])
            html_path = HtmlExporter().export(Path(tmp) / "book.html", title="Книга", chapters=[chapter])
            txt = text_path.read_text(encoding="utf-8")
            html = html_path.read_text(encoding="utf-8")
            self.assertIn("Привет & мир", txt)
            self.assertIn("[Изображение: images/a.gif]", txt)
            self.assertIn("Привет &amp; мир", html)
            self.assertIn("data:image/gif;base64,", html)
            self.assertIn("<p>", html)
            self.assertNotIn("ns0:", html)

    def test_downloader_with_txt_and_html_exporters(self):
        title = SimpleNamespace(id=7, slug_url="7--book", title="Test",
                                authors=("Author",), description="", cover_url=None)
        item = SimpleNamespace(id=11, volume="1", number="1", index=1,
                               name="Chapter 1", branches=[])
        titles, chapters, contents = Mock(), Mock(), Mock()
        titles.get_title.return_value = title
        chapters.get_chapters.return_value = [item]
        contents.get_chapter.return_value = ChapterContent.from_api({
            "id": 11, "volume": "1", "number": "1", "name": "Chapter 1",
            "content": "<p>Hello</p>",
        })
        with tempfile.TemporaryDirectory() as tmp:
            for exporter, ext, marker in (
                (TxtExporter(), "txt", "Hello"),
                (HtmlExporter(), "html", "<p>Hello</p>"),
            ):
                downloader = BookDownloader(titles=titles, chapters=chapters,
                                            contents=contents, exporter=exporter)
                result = downloader.download("7--book", Path(tmp) / ("book." + ext),
                                             cache_dir=tmp, delay=0)
                self.assertIn(marker, result.read_text(encoding="utf-8"))

    def test_html_rejects_missing_image(self):
        chapter = NormalizedChapter(
            "Chapter", '<html xmlns="http://www.w3.org/1999/xhtml">'
            '<body><img src="images/missing.png" /></body></html>'
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "Missing HTML image"):
                HtmlExporter().export(Path(tmp) / "book.html", title="Book",
                                      chapters=[chapter])


if __name__ == "__main__":
    unittest.main()
