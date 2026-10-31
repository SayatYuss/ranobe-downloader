import unittest

from core.title import TitleMetadata, parse_title_reference, summary_as_text


class TitleTests(unittest.TestCase):
    def test_reference_forms(self):
        expected = "55754--cuttlefish-that-loves-diving"
        self.assertEqual(parse_title_reference(expected), expected)
        self.assertEqual(parse_title_reference("55754"), "55754")
        self.assertEqual(
            parse_title_reference(f"https://ranobelib.me/ru/manga/{expected}?from=search"),
            expected,
        )
        self.assertEqual(
            parse_title_reference(f"https://api.imglib.info/api/manga/{expected}"),
            expected,
        )

    def test_disallowed_host(self):
        with self.assertRaises(ValueError):
            parse_title_reference("https://example.com/ru/manga/55754--test")

    def test_summary(self):
        doc = {"type": "doc", "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "First."}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "Second."}]},
        ]}
        self.assertEqual(summary_as_text(doc).strip(), "First.\nSecond.")

    def test_metadata_mapping(self):
        payload = {
            "id": 55754,
            "slug_url": "55754--cuttlefish-that-loves-diving",
            "name": "Embers Ad Infinitum (Novel)",
            "rus_name": "Последнее пламя в долгой ночи",
            "authors": [{"name": "Ai Qianshui de Wuzei"}],
            "summary": {"type": "doc", "content": []},
            "cover": {"default": "https://cover.imglib.info/cover.jpg"},
            "items_count": {"uploaded": 633},
            "metadata": {"count": {"branches": 2}},
        }
        result = TitleMetadata.from_api(payload)
        self.assertEqual(result.title, payload["rus_name"])
        self.assertEqual(result.uploaded_count, 633)
        self.assertEqual(result.branches_count, 2)
        self.assertEqual(result.authors, ("Ai Qianshui de Wuzei",))


if __name__ == "__main__":
    unittest.main()
