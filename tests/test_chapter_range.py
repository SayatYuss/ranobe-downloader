"""Chapter range tests without network or media downloads."""
import unittest
from types import SimpleNamespace

from core.download.range import chapter_number, select_chapter_range


def ch(number, volume="1"):
    return SimpleNamespace(number=str(number), volume=str(volume))


class ChapterRangeTests(unittest.TestCase):
    def test_fractional_inclusive_boundaries(self):
        items = [ch("1"), ch("13.3"), ch("13.4"), ch("14"), ch("45"), ch("46")]
        self.assertEqual([x.number for x in select_chapter_range(items, "13.4", "45")],
                         ["13.4", "14", "45"])

    def test_exact_decimal_precision(self):
        self.assertEqual(chapter_number("13.40"), chapter_number("13.4"))
        items = [ch("13.4"), ch("13.40"), ch("13.41")]
        self.assertEqual(len(select_chapter_range(items, "13.4", "13.40")), 2)

    def test_open_boundaries(self):
        items = [ch("1"), ch("2"), ch("3")]
        self.assertEqual([x.number for x in select_chapter_range(items, None, "2")], ["1", "2"])
        self.assertEqual([x.number for x in select_chapter_range(items, "2", None)], ["2", "3"])
        self.assertIs(select_chapter_range(items), items)

    def test_invalid_or_nonexistent_bounds(self):
        items = [ch("1"), ch("2")]
        for a, z in [("3", None), (None, "3"), ("2", "1"),
                     ("NaN", None), ("1.2.3", None), (True, None)]:
            with self.subTest(a=a, z=z), self.assertRaises(ValueError):
                select_chapter_range(items, a, z)

    def test_duplicate_chapter_number_in_other_volume_is_ambiguous(self):
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            select_chapter_range([ch("1", "1"), ch("1", "2")], "1", None)

    def test_non_numeric_chapter_index_is_rejected_when_filtering(self):
        with self.assertRaisesRegex(ValueError, "Non-numeric"):
            select_chapter_range([ch("prologue")], "1", None)


if __name__ == "__main__":
    unittest.main()
