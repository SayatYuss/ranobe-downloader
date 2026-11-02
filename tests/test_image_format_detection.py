import tempfile
import unittest
from pathlib import Path

from core.download.images import detect_image_format, load_images


class ImageFormatDetectionTests(unittest.TestCase):
    def test_detects_jpeg_even_when_attachment_extension_is_png(self):
        jpeg = bytes.fromhex("ffd8ffe000104a46494600010100000100010000")
        self.assertEqual(detect_image_format(jpeg), ("image/jpeg", "jpg"))

        document = {"type": "doc", "content": [
            {"type": "image", "attrs": {"images": [{"image": "123"}]}}
        ]}
        attachment = {
            "name": "123", "extension": "png",
            "originalUrl": "https://img3.cdnlibs.org/page.png",
        }
        with tempfile.TemporaryDirectory() as directory:
            result = load_images(
                document, [attachment], Path(directory), 1,
                fetch_media=lambda _: jpeg,
                validate_attachment=lambda _: None,
            )
        self.assertEqual(result["123"][0], "images/1-123.jpg")
        self.assertEqual(result["123"][1], jpeg)
        self.assertEqual(result["123"][2], "image/jpeg")

    def test_rejects_unknown_image_bytes(self):
        with self.assertRaises(ValueError):
            detect_image_format(b"<html>not an image</html>")


if __name__ == "__main__":
    unittest.main()
