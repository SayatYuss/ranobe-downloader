import unittest
from io import BytesIO

from core.download.image_optimization import optimize_image


class ImageOptimizationTests(unittest.TestCase):
    def test_preserves_existing_webp(self):
        source = b"RIFFxxxxWEBP"
        self.assertEqual(optimize_image(source, "image/webp"), (source, "image/webp", "webp"))

    def test_invalid_options(self):
        with self.assertRaises(ValueError):
            optimize_image(b"", "image/png", quality=0)

    def test_opaque_png_optimized(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Optional Pillow not installed")
        import random
        rng = random.Random(123)
        pixels = rng.randbytes(200 * 200 * 3)
        source = Image.frombytes("RGB", (200, 200), pixels)
        buf = BytesIO()
        source.save(buf, format="PNG")
        data, media, ext = optimize_image(buf.getvalue(), "image/png", quality=75)
        self.assertEqual(media, "image/jpeg")
        self.assertEqual(ext, "jpg")
        self.assertLess(len(data), len(buf.getvalue()))

    def test_transparent_png_unchanged(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Optional Pillow not installed")
        source = Image.new("RGBA", (10, 10), (255, 0, 0, 50))
        buf = BytesIO()
        source.save(buf, format="PNG")
        self.assertEqual(optimize_image(buf.getvalue(), "image/png"), (buf.getvalue(), "image/png", "png"))
