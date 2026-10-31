"""RanobeLib media policy regression tests."""
import unittest

from providers.libsocial.media_policy import (
    IMAGE_HEADERS, attachment_path, html_image_path, image_urls,
)


class MediaPolicyTests(unittest.TestCase):
    def test_trusted_attachment_url_candidates(self):
        path = "/uploads/ranobe/book/chapters/1/test.png"
        self.assertEqual(attachment_path(path), path)
        self.assertEqual(image_urls(path), (
            "https://ranobelib.me" + path,
            "https://img3.mixlib.me" + path,
        ))
        self.assertEqual(html_image_path("https://ranobelib.me" + path), path)
        self.assertEqual(IMAGE_HEADERS["Referer"], "https://ranobelib.me/")

    def test_invalid_media_urls_are_rejected(self):
        for path in (
            "https://evil.example/uploads/ranobe/test.png",
            "/uploads/ranobe/../test.png",
            "/uploads/ranobe/file.png?token=secret",
            "/other/images/file.png",
            "/uploads/ranobe/test\\\\file.png",
        ):
            with self.subTest(path=path), self.assertRaises(ValueError):
                attachment_path(path)

        for url in (
            "https://evil.example/uploads/ranobe/test.png",
            "//ranobelib.me/uploads/ranobe/test.png",
            "https://ranobelib.me:8443/uploads/ranobe/test.png",
            "https://user@ranobelib.me/uploads/ranobe/test.png",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                html_image_path(url)


if __name__ == "__main__":
    unittest.main()
