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

    def test_reject_empty_chapters_and_bad_xhtml(self):
        exporter = EpubExporter()
        with self.assertRaises(ValueError):
            exporter.export("unused.epub", title="Title", chapters=[])
        with self.assertRaises((ValueError, ElementTree.ParseError)):
            exporter.export("unused.epub", title="Title",
                            chapters=[EpubChapter("Bad", "<html>")])
