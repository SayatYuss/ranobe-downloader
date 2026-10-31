"""Corrupted cache recovery and repeated-request suppression."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from core.download.checkpoint import ChapterCheckpoint
from core.download.fetcher import ChapterFetcher
from core.download.images import load_images


class CacheRecoveryTests(unittest.TestCase):
    def test_chapter_checksum_detects_valid_json_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = ChapterCheckpoint(tmp, 1, None)
            original = {"volume": "1", "number": "1", "content": "<p>original</p>"}
            cache.save(10, original, volume="1", number="1")
            self.assertEqual(cache.load(10, volume="1", number="1"), original)
            cache.path(10).write_text(
                '{"volume":"1","number":"1","content":"<p>tampered</p>"}',
                encoding="utf-8",
            )
            self.assertIsNone(cache.load(10, volume="1", number="1"))

    def test_corruption_triggers_refetch_then_reuses_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = ChapterCheckpoint(tmp, 1, None)
            payload = {"volume": "1", "number": "1", "content": "<p>fresh</p>"}
            cache.save(10, payload, volume="1", number="1")
            cache.path(10).write_text("{}", encoding="utf-8")
            source = Mock()
            source.get_chapter.return_value = SimpleNamespace(data=payload)
            fetcher = ChapterFetcher(source, cache)
            item = SimpleNamespace(id=10, volume="1", number="1")
            first, cached = fetcher.fetch("1--demo", item, resume=True)
            self.assertFalse(cached)
            self.assertEqual(first, payload)
            second, cached = fetcher.fetch("1--demo", item, resume=True)
            self.assertTrue(cached)
            self.assertEqual(second, payload)
            source.get_chapter.assert_called_once()

    def test_corrupt_image_checksum_triggers_redownload(self):
        uid = "image_1"
        document = {"type": "doc", "content": [
            {"type": "image", "attrs": {"images": [{"image": uid}]}}
        ]}
        attachment = {"name": uid, "extension": "gif",
                      "url": "https://example.test/img.gif"}
        original = b"GIF89a" + b"A" * 20
        replacement = b"GIF89a" + b"B" * 20
        download = Mock(side_effect=[original, replacement])
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            args = (document, [attachment], directory, 1)
            kwargs = {"fetch_media": download, "validate_attachment": lambda _: None}
            load_images(*args, **kwargs)
            cached = directory / "images" / "1" / (uid + ".gif")
            cached.write_bytes(b"GIF89a" + b"X" * 20)
            result = load_images(*args, **kwargs)
            self.assertEqual(result[uid][1], replacement)
            load_images(*args, **kwargs)
            self.assertEqual(download.call_count, 2)


if __name__ == "__main__":
    unittest.main()
