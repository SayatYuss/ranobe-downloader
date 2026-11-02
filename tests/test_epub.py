import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile, ZIP_STORED

from core.chapter_xhtml import chapter_to_xhtml
from exporters.epub import EpubChapter, EpubExporter


class EpubExporterTests(unittest.TestCase):
    def test_epub_archive_and_navigation(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "novel.epub"
            document = {"type": "doc", "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Привет & мир"}]}
            ]}
            chapters = [
                EpubChapter("Глава 1", chapter_to_xhtml("Глава 1", document)),
                EpubChapter("Глава 2", chapter_to_xhtml("Глава 2", document)),
            ]
            EpubExporter().export(target, title="Книга & текст", authors=("Автор",), chapters=chapters)
            with ZipFile(target) as archive:
                self.assertEqual(archive.namelist()[0], "mimetype")
                self.assertEqual(archive.getinfo("mimetype").compress_type, ZIP_STORED)
                self.assertEqual(archive.read("mimetype"), b"application/epub+zip")
                for path in ("META-INF/container.xml", "OEBPS/package.opf", "OEBPS/nav.xhtml",
                             "OEBPS/chapter-0001.xhtml", "OEBPS/chapter-0002.xhtml"):
                    ElementTree.fromstring(archive.read(path))
                opf = archive.read("OEBPS/package.opf").decode()
                nav = archive.read("OEBPS/nav.xhtml").decode()
                self.assertIn("Книга &amp; текст", opf)
                self.assertIn("Глава 1", nav)
                self.assertIn("Глава 2", nav)
                self.assertIn("Привет &amp; мир", archive.read("OEBPS/chapter-0001.xhtml").decode())

    def test_embedded_cover_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "cover.epub"
            xhtml = chapter_to_xhtml("Chapter", {"type": "doc", "content": []})
            cover = b"\\xff\\xd8\\xff" + b"fake-jpeg"
            EpubExporter().export(target, title="Book", authors=("Writer",),
                description="Description & details", chapters=[EpubChapter("Chapter", xhtml)],
                cover=cover, cover_media_type="image/jpeg")
            with ZipFile(target) as archive:
                self.assertEqual(archive.read("OEBPS/cover.jpg"), cover)
                package = archive.read("OEBPS/package.opf").decode()
                self.assertIn('properties="cover-image"', package)
                self.assertIn("<dc:creator>Writer</dc:creator>", package)
                self.assertIn("Description &amp; details", package)

    def test_manga_image_pages_get_full_page_styles(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "manga.epub"
            xhtml = chapter_to_xhtml("Chapter 1", {"type": "doc", "content": [
                {"type": "image", "attrs": {"images": [{"image": "1"}]}},
                {"type": "image", "attrs": {"images": [{"image": "2"}]}},
            ]}, images={"1": "images/1.jpg", "2": "images/2.jpg"})
            chapter = EpubChapter(
                "Chapter 1", xhtml,
                (("images/1.jpg", b"jpeg-one", "image/jpeg"),
                 ("images/2.jpg", b"jpeg-two", "image/jpeg")),
                image_pages=True,
            )
            EpubExporter().export(target, title="Manga", chapters=[chapter])
            with ZipFile(target) as archive:
                page = archive.read("OEBPS/chapter-0001.xhtml").decode()
                self.assertIn("object-fit: contain", page)
                self.assertIn("page-break-after: always", page)
                self.assertIn("width: 100vw", page)
                self.assertEqual(page.count("<img "), 2)

    def test_reject_invalid_cover_type(self):
        xhtml = chapter_to_xhtml("Chapter", {"type": "doc", "content": []})
        with self.assertRaises(ValueError):
            EpubExporter().export("unused.epub", title="Book",
                chapters=[EpubChapter("Chapter", xhtml)],
                cover=b"not-an-image", cover_media_type="image/gif")

    def test_reject_empty_chapters_and_bad_xhtml(self):
        exporter = EpubExporter()
        with self.assertRaises(ValueError):
            exporter.export("unused.epub", title="Title", chapters=[])
        with self.assertRaises((ValueError, ElementTree.ParseError)):
            exporter.export("unused.epub", title="Title",
                            chapters=[EpubChapter("Bad", "<html>")])
