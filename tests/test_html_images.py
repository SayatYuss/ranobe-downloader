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

    def test_missing_attachment_uses_safe_fallback(self):
        path = "/uploads/ranobe/14841/chapters/123/missing.jpg"
        attachments = list(self.attachments)
        sources, ids = resolve_html_images(
            '<img src="' + path + '">', attachments,
        )
        self.assertEqual(len(ids), 1)
        self.assertEqual(sources[path], ids[0])
        self.assertEqual(attachments[-1]["originalUrl"], path)

    def test_unsupported_image_path_without_attachment_fails(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            resolve_html_images(
                '<img src="/uploads/ranobe/14841/other/missing.jpg">',
                list(self.attachments),
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
        self.assertEqual(len(ids), 1)
        self.assertEqual(len(ids[0]), 64)
        self.assertEqual(sources[self.path], ids[0])
        self.assertEqual(attachments[0]["originalUrl"], self.path)

    def test_slug_title_and_named_html_image(self):
        path = "/uploads/ranobe/the-beginning-after-the-end-novel/chapters/2066341/karta-dikatena_NUh2.png"
        attachments = []
        sources, ids = resolve_html_images('<img src="' + path + '">', attachments)
        self.assertEqual(len(ids), 1)
        self.assertEqual(sources[path], ids[0])
        self.assertEqual(attachments[0]["originalUrl"], path)
        self.assertEqual(attachments[0]["extension"], "png")

    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):
            resolve_html_images(
                '<img src="/uploads/ranobe/title/chapters/1/../secret.png">', [],
            )

    def test_non_image_html_unchanged(self):
        self.assertEqual(resolve_html_images("<p>Text</p>", []), ({}, []))


if __name__ == "__main__":
    unittest.main()
