"""Download optimization regression tests."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from core.download.processor import ContentProcessor
from exporters.atomic import atomic_destination
from exporters.epub import EpubChapter, EpubExporter
from exporters.text import HtmlExporter, TxtExporter


class DownloadOptimizationTests(unittest.TestCase):
    def test_txt_skips_media_transport(self):
        media = Mock()
        media.resolve_html_images.return_value = ({"/uploads/test.png": "img1"}, ["img1"])
        item = SimpleNamespace(id=1, volume="1", number="1", name="Chapter")
        chapter = ContentProcessor(media=media).process(
            {"id": 1, "name": "Chapter", "content": '<p>Hello</p><img src="/uploads/test.png">'},
            item, Path("unused"), skip_images=True,
        )
        media.load_images.assert_not_called()
        self.assertEqual(chapter.images, ())
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "book.txt"
            TxtExporter().export(target, title="Book", chapters=[chapter])
            self.assertIn("Hello", target.read_text())

    def test_atomic_failure_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "book.txt"
            target.write_text("original")
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                with atomic_destination(target) as temporary:
                    temporary.write_text("new")
                    raise RuntimeError("interrupted")
            self.assertEqual(target.read_text(), "original")
            self.assertEqual(sorted(x.name for x in Path(tmp).iterdir()), ["book.txt"])

    def test_atomic_success_replaces_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "book.txt"
            target.write_text("original")
            with atomic_destination(target) as temporary:
                temporary.write_text("replacement")
            self.assertEqual(target.read_text(), "replacement")


if __name__ == "__main__":
    unittest.main()
