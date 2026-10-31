import unittest
from unittest.mock import patch

from core.download.plan import DownloadPlan, Translation, make_translations
from interfaces.cli.translation_selector import select_translation


class TranslationSelectionTests(unittest.TestCase):
    def setUp(self):
        self.options = (
            Translation(10, 12, 'First team'),
            Translation(20, 8, 'Second team'),
        )

    def test_single_translation_auto_selected(self):
        self.assertEqual(select_translation(self.options[:1], interactive=False), 10)

    def test_multiple_translations_without_tty_raise(self):
        with patch('sys.stdin.isatty', return_value=False):
            with self.assertRaisesRegex(ValueError, '--branch'):
                select_translation(self.options)

    def test_interactive_choice(self):
        with patch('sys.stdin.isatty', return_value=True), patch('builtins.input', return_value='2'):
            self.assertEqual(select_translation(self.options), 20)

    def test_interactive_retries_invalid_input(self):
        with patch('sys.stdin.isatty', return_value=True), patch('builtins.input', side_effect=['oops', '3', '1']):
            self.assertEqual(select_translation(self.options), 10)

    def test_cancel(self):
        with patch('sys.stdin.isatty', return_value=True), patch('builtins.input', return_value='q'):
            with self.assertRaisesRegex(ValueError, 'cancelled'):
                select_translation(self.options)

    def test_unbranched_title(self):
        self.assertIsNone(select_translation((), interactive=False))


if __name__ == '__main__':
    unittest.main()
