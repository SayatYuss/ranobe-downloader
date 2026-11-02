import unittest

from providers.mangalib.chapter_content import ChapterContentProvider, _page_attachment
from providers.mangalib.chapters import ChapterProvider
from providers.mangalib.references import is_mangalib_reference, parse_title_reference
from providers.mangalib.titles import TitleProvider


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params))
        return {"data": self.responses[path]}


class MangaLibProviderTests(unittest.TestCase):
    def test_reference_forms_and_host_validation(self):
        slug = "102416--yomi-no-tsugai"
        self.assertEqual(parse_title_reference(slug), slug)
        self.assertEqual(parse_title_reference("102416"), "102416")
        self.assertEqual(
            parse_title_reference(f"https://mangalib.me/ru/manga/{slug}"), slug
        )
        self.assertTrue(is_mangalib_reference(f"https://mangalib.me/ru/manga/{slug}"))
        self.assertFalse(is_mangalib_reference("https://ranobelib.me/ru/manga/123--x"))
        with self.assertRaises(ValueError):
            parse_title_reference("https://example.com/manga/123--x")

    def test_title_mapping(self):
        slug = "102416--yomi-no-tsugai"
        client = FakeClient({f"/manga/{slug}": {
            "id": 102416, "slug_url": slug, "name": "Yomi no tsugai",
            "rus_name": "Цугаи загробного мира",
            "authors": [{"name": "Hiromu Arakawa"}],
            "summary": {"type": "doc", "content": []},
            "cover": {"default": "https://cover.imglib.info/uploads/cover.jpg"},
            "releaseDate": "2021", "genres": [{"name": "Фэнтези"}],
            "items_count": {"uploaded": 64}, "metadata": {"count": {"branches": 1}},
        }})
        title = TitleProvider(client).get_title(slug)
        self.assertEqual(title.id, 102416)
        self.assertEqual(title.title, "Цугаи загробного мира")
        self.assertEqual(title.authors, ("Hiromu Arakawa",))
        self.assertEqual(title.genres, ("Фэнтези",))

    def test_chapter_index_maps_translation_branches(self):
        slug = "102416--yomi-no-tsugai"
        client = FakeClient({f"/manga/{slug}/chapters": [{
            "id": 1734852, "index": 1, "volume": "1", "number": "1",
            "name": "Аса и Юру", "branches_count": 1,
            "branches": [{"id": 1734852, "branch_id": 7,
                          "teams": [{"id": 21921, "name": "Spokon Jutsu Team"}]}],
        }]})
        chapters = ChapterProvider(client).get_chapters(slug)
        self.assertEqual(chapters[0].number, "1")
        self.assertEqual(chapters[0].branches[0].branch_id, 7)
        self.assertEqual(chapters[0].branches[0].teams[0].name, "Spokon Jutsu Team")

    def test_chapter_pages_become_shared_image_document(self):
        slug = "102416--yomi-no-tsugai"
        client = FakeClient({f"/manga/{slug}/chapter": {
            "id": 1734852, "name": "Аса и Юру", "volume": "1", "number": "1",
            "pages": [
                {"id": 20, "slug": 2, "url": "//manga/yomi-no-tsugai/chapters/1/page-2.png"},
                {"id": 10, "slug": 1, "url": "//manga/yomi-no-tsugai/chapters/1/page-1.jpg"},
            ],
        }})
        content = ChapterContentProvider(client).get_chapter(
            slug, volume="1", number="1", branch_id=7
        )
        self.assertEqual(client.calls[0][1], {
            "volume": "1", "number": "1", "branch_id": 7
        })
        self.assertEqual(
            [item["name"] for item in content.data["attachments"]], ["10", "20"]
        )
        self.assertEqual(
            content.data["attachments"][0]["originalUrl"],
            "https://img3.cdnlibs.org/manga/yomi-no-tsugai/chapters/1/page-1.jpg",
        )
        self.assertEqual(
            content.content["content"][0]["attrs"]["images"][0]["image"], "10"
        )

    def test_page_url_rejects_untrusted_hosts(self):
        with self.assertRaises(ValueError):
            _page_attachment({"id": 1, "url": "https://evil.example/page.png"})


if __name__ == "__main__":
    unittest.main()
