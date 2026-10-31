"""Offline end-to-end tests: chapter provider -> downloader -> actual EPUB ZIP."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_STORED

from core.book_downloader import BookDownloader
from core.chapter_content import ChapterContent


XHTML = "{http://www.w3.org/1999/xhtml}"
OPF = "{http://www.idpf.org/2007/opf}"
DC = "{http://purl.org/dc/elements/1.1/}"
EPUB = "{http://www.idpf.org/2007/ops}"
GIF = b"GIF89a" + b"0" * 20


def chapter(number, chapter_id):
    return SimpleNamespace(
        id=chapter_id, volume="1", number=str(number), index=number,
        name=f"Глава {number}", branches=[],
    )


class EpubIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.client = Mock()
        self.downloader = BookDownloader(self.client)
        self.downloader.titles.get_title = Mock(return_value=SimpleNamespace(
            id=100, slug_url="100--book", title="Книга & тест",
            authors=("Автор",), description="Описание", cover_url=None))
        self.downloader.chapters.get_chapters = Mock(return_value=[
            chapter(2, 102), chapter(1, 101)
        ])
        self.uid = "image_i9wg"
        self.image_path = "/uploads/ranobe/book/chapters/102/image_i9wg.gif"
        attachment = {"name": self.uid, "extension": "gif", "originalUrl": self.image_path}
        self.payloads = {
            "1": {"id": 101, "volume": "1", "number": "1", "name": "Первая", "content": "<p>Первый &amp; текст</p>"},
            "2": {
                "id": 102, "volume": "1", "number": "2", "name": "Вторая",
                "content": {"type": "doc", "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "Второй текст"}]},
                    {"type": "image", "attrs": {"images": [{"image": self.uid}]}}
                ]},
                "attachments": [attachment]
            },
        }
        self.downloader.contents.get_chapter = Mock(
            side_effect=lambda reference, *, volume, number, branch_id=None:
            ChapterContent.from_api(self.payloads[number])
        )

    def _download(self, *, resume=False):
        destination = self.root / "novel.epub"
        with patch("core.download.images._fetch", return_value=GIF):
            return self.downloader.download(
                "100--book", destination, cache_dir=self.root / "cache",
                delay=0, resume=resume,
            )

    def test_real_epub_archive_navigation_spine_and_images(self):
        destination = self._download()
        self.assertTrue(destination.is_file())
        with ZipFile(destination) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.namelist()[0], "mimetype")
            self.assertEqual(archive.read("mimetype"), b"application/epub+zip")
            self.assertEqual(archive.getinfo("mimetype").compress_type, ZIP_STORED)

            container = ET.fromstring(archive.read("META-INF/container.xml"))
            rootfile = container.find(".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile")
            self.assertEqual(rootfile.attrib["full-path"], "OEBPS/package.opf")

            package = ET.fromstring(archive.read("OEBPS/package.opf"))
            self.assertEqual(package.find(f".//{DC}title").text, "Книга & тест")
            manifest = {item.attrib["id"]: item.attrib
                        for item in package.findall(f".//{OPF}manifest/{OPF}item")}
            spine = [item.attrib["idref"]
                     for item in package.findall(f".//{OPF}spine/{OPF}itemref")]
            self.assertEqual(spine, ["c1", "c2"])
            self.assertEqual([manifest[item]["href"] for item in spine],
                             ["chapter-0001.xhtml", "chapter-0002.xhtml"])

            nav = ET.fromstring(archive.read("OEBPS/nav.xhtml"))
            links = nav.findall(f".//{XHTML}a")
            self.assertEqual([(link.text, link.attrib["href"]) for link in links],
                             [("Первая", "chapter-0001.xhtml"),
                              ("Вторая", "chapter-0002.xhtml")])

            first = ET.fromstring(archive.read("OEBPS/chapter-0001.xhtml"))
            second = ET.fromstring(archive.read("OEBPS/chapter-0002.xhtml"))
            self.assertIn("Первый & текст", "".join(first.itertext()))
            self.assertIn("Второй текст", "".join(second.itertext()))
            images = second.findall(f".//{XHTML}img")
            self.assertEqual(len(images), 1)
            image_href = images[0].attrib["src"]
            self.assertEqual(image_href, f"images/102-{self.uid}.gif")
            self.assertEqual(archive.read("OEBPS/" + image_href), GIF)
            self.assertTrue(any(item["href"] == image_href and
                                item["media-type"] == "image/gif"
                                for item in manifest.values()))
            for item in manifest.values():
                self.assertIn("OEBPS/" + item["href"], archive.namelist())

    def test_resume_uses_cached_chapters_and_produces_valid_epub(self):
        self._download()
        self.downloader.contents.get_chapter.reset_mock()
        result = self._download(resume=True)
        self.downloader.contents.get_chapter.assert_not_called()
        with ZipFile(result) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(len([path for path in archive.namelist()
                                  if path.startswith("OEBPS/chapter-")]), 2)

    def test_paid_chapter_is_skipped_and_reported(self):
        self.payloads["2"] = {
            "id": 102, "name": "Вторая",
            "restricted_view": {"is_open": False, "price": 10}
        }
        from core.download.statistics import DownloadStatistics
        received = []
        destination = self.root / "novel.epub"
        with patch("core.download.images._fetch", return_value=GIF):
            self.downloader.download(
                "100--book", destination, cache_dir=self.root / "cache",
                delay=0, statistics=received.append,
            )
        with ZipFile(destination) as archive:
            self.assertIsNone(archive.testzip())
            self.assertIn("OEBPS/chapter-0001.xhtml", archive.namelist())
            self.assertNotIn("OEBPS/chapter-0002.xhtml", archive.namelist())
        self.assertEqual(received[0].chapters, 1)
        self.assertEqual(received[0].skipped_paid_chapters, ("1/2 — Вторая",))

    def test_all_paid_chapters_rejects_empty_book(self):
        self.payloads["1"] = {
            "id": 101, "name": "Первая",
            "restricted_view": {"is_open": False, "price": 10}
        }
        self.payloads["2"] = {
            "id": 102, "name": "Вторая",
            "restricted_view": {"is_open": False, "price": 10}
        }
        with self.assertRaisesRegex(ValueError, "No accessible chapters"):
            self._download()
        self.assertFalse((self.root / "novel.epub").exists())

    def test_html_image_is_packaged(self):
        self.payloads["2"]["content"] = (
            '<p>С иллюстрацией</p><img src="' + self.image_path + '">'
        )
        destination = self._download()
        with ZipFile(destination) as archive:
            chapter_xml = ET.fromstring(archive.read("OEBPS/chapter-0002.xhtml"))
            img = chapter_xml.find(f".//{XHTML}img")
            self.assertIsNotNone(img)
            self.assertEqual(archive.read("OEBPS/" + img.attrib["src"]), GIF)


if __name__ == "__main__":
    unittest.main()
