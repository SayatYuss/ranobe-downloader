"""Generic image caching with a non-RanobeLib media transport."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from core.download.images import load_images


class AlternateMediaTests(unittest.TestCase):
    def test_alternate_provider_download_and_cache(self):
        document = {"type": "doc", "content": [
            {"type": "image", "attrs": {"images": [{"image": "photo_1"}]}}
        ]}
        attachment = {"name": "photo_1", "extension": "gif",
                      "originalUrl": "https://pictures.example/one.gif"}
        payload = b"GIF89a" + b"0" * 20
        fetcher = Mock(return_value=payload)
        def validate(path):
            if path != "https://pictures.example/one.gif":
                raise ValueError("Invalid custom image URL")
        with tempfile.TemporaryDirectory() as tmp:
            first = load_images(document, [attachment], Path(tmp), 7,
                                fetch_media=fetcher, validate_attachment=validate)
            second = load_images(document, [attachment], Path(tmp), 7,
                                 fetch_media=fetcher, validate_attachment=validate)
        self.assertEqual(first, second)
        self.assertEqual(fetcher.call_count, 1)
        self.assertEqual(first["photo_1"][1], payload)

    def test_provider_url_is_validated_even_when_cached(self):
        doc = {"type": "image", "attrs": {"images": [{"image": "photo_1"}]}}
        attachment = {"name": "photo_1", "extension": "gif", "originalUrl": "unsafe"}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "blocked"):
                load_images(doc, [attachment], Path(tmp), 7,
                            fetch_media=lambda _: b"GIF89a123",
                            validate_attachment=lambda path: (_ for _ in ()).throw(
                                ValueError("blocked")))
