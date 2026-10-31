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

    def test_named_image_identifier_is_packaged(self):
        uid = "image_i9wg"
        document = {"type": "doc", "content": [
            {"type": "image", "attrs": {"images": [{"image": uid}]}}
        ]}
        attachments = [{"name": uid, "extension": "gif",
                        "originalUrl": "/uploads/ranobe/book/chapters/123/image.gif"}]
        with tempfile.TemporaryDirectory() as root:
            with patch("core.download.images._fetch", return_value=GIF):
                media = load_images(document, attachments, Path(root), 123)
            self.assertIn(uid, media)
            self.assertEqual(media[uid][0], "images/123-image_i9wg.gif")
            chapter = EpubChapter("Test", chapter_to_xhtml(
                "Test", document, images={uid: media[uid][0]}), tuple(media.values()))
            destination = Path(root) / "named.epub"
            EpubExporter().export(destination, title="Book", chapters=[chapter])
            with ZipFile(destination) as archive:
                self.assertEqual(archive.read("OEBPS/images/123-image_i9wg.gif"), GIF)

    def test_image_identifier_rejects_unsafe_names(self):
        from core.download.images import valid_image_identifier
        self.assertTrue(valid_image_identifier("image_i9wg"))
        self.assertTrue(valid_image_identifier(UUID))
        for uid in ("../oops", "image/name", "image\\\\name", "image name",
                    "", "x" * 129, "ö", "image.png"):
            self.assertFalse(valid_image_identifier(uid), uid)

    def test_large_image_limit_and_streaming(self):
        from core.download.images import MAX_SIZE, _fetch
        from unittest.mock import MagicMock
        self.assertEqual(MAX_SIZE, 30 * 1024 * 1024)
        response = MagicMock()
        response.headers = {}
        response.is_redirect = False
        response.iter_bytes.return_value = iter([b"x" * (16 * 1024 * 1024)])
        client = MagicMock()
        client.__enter__.return_value.stream.return_value.__enter__.return_value = response
        with patch("core.download.images.httpx.Client", return_value=client):
            self.assertEqual(len(_fetch("https://ranobelib.me/test")), 16 * 1024 * 1024)
        response.iter_bytes.return_value = iter([b"x" * (16 * 1024 * 1024),
                                                  b"x" * (15 * 1024 * 1024)])
        with patch("core.download.images.httpx.Client", return_value=client):
            with self.assertRaisesRegex(ValueError, "30 MiB"):
                _fetch("https://ranobelib.me/test")

    def test_large_content_length_is_rejected_before_streaming(self):
        from core.download.images import MAX_SIZE, _fetch
        from unittest.mock import MagicMock
        response = MagicMock()
        response.headers = {"Content-Length": str(MAX_SIZE + 1)}
        response.is_redirect = False
        client = MagicMock()
        client.__enter__.return_value.stream.return_value.__enter__.return_value = response
        with patch("core.download.images.httpx.Client", return_value=client):
            with self.assertRaisesRegex(ValueError, "30 MiB"):
                _fetch("https://ranobelib.me/test")
        response.iter_bytes.assert_not_called()
