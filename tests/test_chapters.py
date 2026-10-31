import unittest

from core.chapter import Chapter
from providers.libsocial.chapters import ChapterProvider


SAMPLE = {
    "id": 223269,
    "index": 1,
    "volume": "1",
    "number": "1.5",
    "name": "Extra",
    "branches_count": 2,
    "branches": [
        {"id": 223269, "branch_id": 4667, "teams": [{"id": 1273, "name": "Nippa"}], "user": {"username": "Alice"}},
        {"id": 777, "branch_id": 4666, "teams": [{"id": 587, "name": "Japit"}]},
    ],
}


class FakeClient:
    def __init__(self, data):
        self.data = data
        self.path = None

    def get(self, path):
        self.path = path
        return {"data": self.data}


class ChapterTests(unittest.TestCase):
    def test_mapping_preserves_fractional_number_and_branches(self):
        chapter = Chapter.from_api(SAMPLE)
        self.assertEqual(chapter.number, "1.5")
        self.assertEqual(chapter.volume, "1")
        self.assertEqual(chapter.branches_count, 2)
        self.assertEqual(chapter.branches[0].branch_id, 4667)
        self.assertEqual(chapter.branches[0].teams[0].name, "Nippa")
        self.assertEqual(chapter.branches[0].username, "Alice")

    def test_provider_fetches_chapters_without_changing_order(self):
        fake = FakeClient([SAMPLE, {**SAMPLE, "id": 15, "number": "1"}])
        chapters = ChapterProvider(fake).get_chapters("55754--cuttlefish-that-loves-diving")
        self.assertEqual(fake.path, "/manga/55754--cuttlefish-that-loves-diving/chapters")
        self.assertEqual([chapter.number for chapter in chapters], ["1.5", "1"])

    def test_invalid_payload_fails(self):
        with self.assertRaises(ValueError):
            ChapterProvider(FakeClient({})).get_chapters("55754")


if __name__ == "__main__":
    unittest.main()
