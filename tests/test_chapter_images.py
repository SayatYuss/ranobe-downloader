import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from xml.etree import ElementTree

from core.chapter_xhtml import chapter_to_xhtml
from core.download.images import image_refs, load_images
from exporters.epub import EpubChapter, EpubExporter


GIF = b"GIF89a" + b"0" * 20
UUID = "5ea9d6f9-f251-49f1-8520-26f9ba30aecd"
DOCUMENT = {"type": "doc", "content": [{
    "type": "image", "attrs": {"images": [{"image": UUID}]}
}]}
ATTACHMENTS = [{"name": UUID, "extension": "gif",
                "originalUrl": "/uploads/ranobe/246638/chapters/4603475/" + UUID + ".gif"}]


class ChapterImageTests(unittest.TestCase):
    def test_image_packaged_and_cached(self):
        with tempfile.TemporaryDirectory() as root:
            with patch("core.download.images._fetch", return_value=GIF) as fetch:
                first = load_images(DOCUMENT, ATTACHMENTS, Path(root), 4603475)
                second = load_images(DOCUMENT, ATTACHMENTS, Path(root), 4603475)
                self.assertEqual(first, second)
                self.assertEqual(fetch.call_count, 1)
            chapter = EpubChapter("Test", chapter_to_xhtml(
                "Test", DOCUMENT, images={uid: image[0] for uid, image in first.items()}),
                tuple(first.values()))
            target = Path(root) / "image.epub"
            EpubExporter().export(target, title="Book", chapters=[chapter])
            with ZipFile(target) as archive:
                path = "OEBPS/images/4603475-" + UUID + ".gif"
                self.assertEqual(archive.read(path), GIF)
                self.assertIn(b'image/gif', archive.read("OEBPS/package.opf"))
                chapter_xml = archive.read("OEBPS/chapter-0001.xhtml")
                ElementTree.fromstring(chapter_xml)
                self.assertIn(("images/4603475-" + UUID + ".gif").encode(), chapter_xml)

    def test_missing_attachment_is_error(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "missing"):
                load_images(DOCUMENT, [], Path(root), 4603475)

    def test_unresolved_image_cannot_be_silently_skipped(self):
        with self.assertRaisesRegex(ValueError, "not resolved"):
            chapter_to_xhtml("Test", DOCUMENT)

    def test_reject_untrusted_attachment_path(self):
        with tempfile.TemporaryDirectory() as root:
            fake = [{"name": UUID, "extension": "gif",
                     "originalUrl": "https://untrusted.example/image.gif"}]
            with self.assertRaisesRegex(ValueError, "Invalid attachment path"):
                load_images(DOCUMENT, fake, Path(root), 4603475)
