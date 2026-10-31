import unittest

from core.download.html_images import resolve_html_images
from core.chapter_xhtml import chapter_to_xhtml


class HtmlImagesTests(unittest.TestCase):
    def setUp(self):
        self.uid = "aabbccdd-1111-2222-3333-444455556666"
        self.path = "/uploads/ranobe/14841/chapters/123/" + self.uid + ".jpg"
        self.attachments = [{
            "name": self.uid, "extension": "jpg",
            "originalUrl": self.path, "url": self.path,
        }]

    def test_resolves_and_renders_in_order(self):
        html = '<p>Before</p><img src="' + self.path + '"><p>After</p>'
        sources, ids = resolve_html_images(html, self.attachments)
        self.assertEqual(ids, [self.uid])
        rendered = chapter_to_xhtml(
            "Chapter", html,
            html_images={src: "images/123-image.jpg" for src in sources},
        )
        self.assertTrue(rendered.index("Before") < rendered.index("<img") < rendered.index("After"))

    def test_approved_absolute_url(self):
        src = "https://ranobelib.me" + self.path
        sources, ids = resolve_html_images('<img src="' + src + '"/>', self.attachments)
        self.assertEqual(sources[src], self.uid)
        self.assertEqual(ids, [self.uid])

    def test_blocks_external_host(self):
        with self.assertRaisesRegex(ValueError, "Untrusted"):
            resolve_html_images('<img src="https://evil.example/a.jpg">', self.attachments)

    def test_missing_attachment_fails(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            resolve_html_images(
                '<img src="/uploads/ranobe/14841/chapters/123/missing.jpg">',
                self.attachments,
            )

    def test_duplicate_image_is_embedded_once(self):
        html = '<img src="' + self.path + '"><img src="' + self.path + '">'
        _, ids = resolve_html_images(html, self.attachments)
        self.assertEqual(ids, [self.uid])

    def test_legacy_url_without_attachments(self):
        attachments = []
        sources, ids = resolve_html_images(
            '<img src="' + self.path + '">', attachments,
        )
        self.assertEqual(ids, [self.uid])
        self.assertEqual(sources[self.path], self.uid)
        self.assertEqual(attachments[0]["originalUrl"], self.path)

    def test_non_image_html_unchanged(self):
        self.assertEqual(resolve_html_images("<p>Text</p>", []), ({}, []))


if __name__ == "__main__":
    unittest.main()
