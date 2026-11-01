"""Selection by chapter IDs follows reading order, not ID values."""
import unittest
from types import SimpleNamespace
from core.download.id_range import select_chapter_id_range


def chapter(cid, vol, num):
    return SimpleNamespace(id=cid, volume=vol, number=num)


class ChapterIdRangeTests(unittest.TestCase):
    def test_duplicate_numbers_different_volumes(self):
        items = [chapter(90, "1", "4"), chapter(5, "1", "5"),
                 chapter(70, "2", "4"), chapter(2, "2", "5")]
        self.assertEqual([c.id for c in select_chapter_id_range(items, 5, 2)], [5, 70, 2])
        self.assertEqual([c.id for c in select_chapter_id_range(items, 70)], [70, 2])
        self.assertEqual([c.id for c in select_chapter_id_range(items, None, 5)], [90, 5])

    def test_boundaries_validated(self):
        items = [chapter(7, "1", "1"), chapter(10, "1", "2")]
        for start, end in [(10, 7), (1, None), (None, 9), (True, None),
                           (0, None), ("7", None), (None, -1)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                select_chapter_id_range(items, start, end)

    def test_duplicate_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            select_chapter_id_range([chapter(3, "1", "1"), chapter(3, "2", "1")], 3)

    def test_no_selection_keeps_legacy_behavior(self):
        items = [chapter(3, "1", "1")]
        self.assertIs(select_chapter_id_range(items), items)


if __name__ == "__main__":
    unittest.main()
