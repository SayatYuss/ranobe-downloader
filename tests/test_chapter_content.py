import unittest

from core.chapter_content import ChapterContent
from providers.libsocial.chapter_content import ChapterContentProvider


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.path = None
        self.params = None

    def get(self, path, params=None):
        self.path = path
        self.params = params
        return {"data": self.payload}


class ChapterContentTests(unittest.TestCase):
    def test_request_with_branch(self):
        fake = FakeClient({"name": "Chapter 1", "content": "<p>Hello</p>"})
        chapter = ChapterContentProvider(fake).get_chapter(
            "55754--cuttlefish-that-loves-diving",
            volume="1", number="1.5", branch_id=27521,
        )
        self.assertEqual(fake.path, "/manga/55754--cuttlefish-that-loves-diving/chapter")
        self.assertEqual(fake.params, {"volume": "1", "number": "1.5", "branch_id": 27521})
        self.assertEqual(chapter.content, "<p>Hello</p>")
        self.assertEqual(chapter.title, "Chapter 1")

    def test_optional_branch_and_schema_preserved(self):
        structured = {"type": "doc", "content": [{"type": "paragraph"}]}
        fake = FakeClient({"content": structured, "pages": [{"url": "/page.jpg"}]})
        chapter = ChapterContentProvider(fake).get_chapter("55754", volume="0", number="2")
        self.assertEqual(fake.params, {"volume": "0", "number": "2"})
        self.assertEqual(chapter.content, structured)
        self.assertEqual(chapter.pages, [{"url": "/page.jpg"}])

    def test_paid_unopened_chapter(self):
        chapter = ChapterContent.from_api({
            "id": 4693476, "restricted_view": {"is_open": False, "price": 10},
        })
        self.assertEqual(chapter.unavailable_reason, "paid_content")
        self.assertEqual(chapter.restricted_view["price"], 10)

    def test_purchased_chapter_with_content(self):
        chapter = ChapterContent.from_api({
            "content": {"type": "doc", "content": []},
            "restricted_view": {"is_open": False, "price": 10},
        })
        self.assertIsNone(chapter.unavailable_reason)

    def test_missing_content_without_restriction(self):
        chapter = ChapterContent.from_api({"id": 42})
        self.assertEqual(chapter.unavailable_reason, "missing_content")

    def test_unknown_payload_type_stays_unsupported(self):
        chapter = ChapterContent.from_api({"content": 123})
        self.assertIsNone(chapter.unavailable_reason)

    def test_reject_invalid_number(self):
        fake = FakeClient({})
        with self.assertRaises(ValueError):
            ChapterContentProvider(fake).get_chapter("55754", volume="1", number="")

    def test_reject_invalid_api_data(self):
        with self.assertRaises(ValueError):
            ChapterContent.from_api([])


if __name__ == "__main__":
    unittest.main()
