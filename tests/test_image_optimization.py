import unittest
from io import BytesIO

from core.download.image_optimization import optimize_image


class ImageOptimizationTests(unittest.TestCase):
    def test_preserves_existing_webp(self):
        source = b"RIFFxxxxWEBP"
        self.assertEqual(optimize_image(source, "image/webp"), (source, "image/webp", "webp"))

    def test_jpeg_quality_recompression(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Optional Pillow not installed")
        import random
        source = Image.frombytes("RGB", (300, 300), random.Random(1234).randbytes(270000))
        buf = BytesIO()
        source.save(buf, format="JPEG", quality=98)
        data, media, ext = optimize_image(buf.getvalue(), "image/jpeg", quality=55)
        self.assertEqual((media, ext), ("image/jpeg", "jpg"))
        self.assertLess(len(data), len(buf.getvalue()))

    def test_webp_quality_recompression(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Optional Pillow not installed")
        import random
        source = Image.frombytes("RGB", (300, 300), random.Random(4321).randbytes(270000))
        buf = BytesIO()
        source.save(buf, format="WEBP", quality=98)
        data, media, ext = optimize_image(buf.getvalue(), "image/webp", quality=45)
        self.assertEqual((media, ext), ("image/webp", "webp"))
        self.assertLess(len(data), len(buf.getvalue()))

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

    def test_nearly_opaque_png_becomes_jpeg(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Optional Pillow not installed")
        import random
        source = Image.frombytes("RGB", (200, 200), random.Random(42).randbytes(120000))
        rgba = source.convert("RGBA")
        rgba.putalpha(Image.new("L", rgba.size, 254))
        buf = BytesIO()
        rgba.save(buf, format="PNG")
        payload, mime, ext = optimize_image(buf.getvalue(), "image/png", quality=75)
        self.assertEqual((mime, ext), ("image/jpeg", "jpg"))
        self.assertLess(len(payload), len(buf.getvalue()))

    def test_meaningful_alpha_preserved(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Optional Pillow not installed")
        rgba = Image.new("RGBA", (10, 10), (20, 40, 60, 249))
        buf = BytesIO()
        rgba.save(buf, format="PNG")
        self.assertEqual(optimize_image(buf.getvalue(), "image/png"),
                         (buf.getvalue(), "image/png", "png"))
