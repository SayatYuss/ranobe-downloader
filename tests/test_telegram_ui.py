"""Tests for pure Telegram UI selection helpers (no Telegram API requests)."""
import unittest
from types import SimpleNamespace

try:
    from interfaces.telegram.ui import Session, available_branches, range_from_indices, format_size, create_application
except ImportError:
    Session = None


@unittest.skipUnless(Session is not None, "Install optional telegram dependencies")
class TelegramUiTests(unittest.TestCase):
    def test_chapter_bounds(self):
        chapters = [
            {"id": 100, "number": "1", "volume": "1"},
            {"id": 222, "number": "13.4", "volume": "1"},
            {"id": 101, "number": "45", "volume": "1"},
        ]
        self.assertEqual(range_from_indices(chapters, 1, 2), (222, 101))
        self.assertEqual(range_from_indices(chapters, None, 2), (None, 101))
        self.assertEqual(range_from_indices(chapters, 1, None), (222, None))
        for start, end in [(2, 1), (-1, 1), (0, 3)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                range_from_indices(chapters, start, end)

    def test_single_or_unbranched(self):
        self.assertEqual(available_branches(SimpleNamespace(translations=())), ())
        book = SimpleNamespace(translations=(SimpleNamespace(branch_id=7),))
        self.assertEqual(available_branches(book)[0].branch_id, 7)

    def test_limits(self):
        self.assertEqual(format_size(45 * 1024**2), "45.0 МиБ")
        with self.assertRaises(ValueError):
            create_application("")
        with self.assertRaises(ValueError):
            create_application("fake-token", max_concurrent=0)


if __name__ == "__main__":
    unittest.main()
