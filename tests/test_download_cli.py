"""CLI output filename and paid chapter reporting tests."""
import argparse
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.download.statistics import DownloadStatistics
from interfaces.cli.download import configure_parser, execute, _print_summary


class DownloadCliTests(unittest.TestCase):
    def test_default_filename_includes_slug_and_branch(self):
        parser = argparse.ArgumentParser()
        configure_parser(parser)
        args = parser.parse_args(["100--test", "--branch", "77", "--format", "txt"])
        plan = SimpleNamespace(title=SimpleNamespace(
            id=100, slug_url="100--test", title="Book"), translations=())
        with tempfile.TemporaryDirectory() as tmp:
            args.output = None
            with patch("interfaces.cli.download.LibSocialClient") as client, patch(
                "interfaces.cli.download.KeyringTokenStorage"
            ), patch("interfaces.cli.download.BookDownloader") as downloader, patch(
                "interfaces.cli.download.Path", wraps=Path
            ):
                downloader.return_value.prepare.return_value = plan
                downloader.return_value.download.return_value = Path("output/100--test_77.txt")
                execute(args)
                self.assertEqual(
                    downloader.return_value.download.call_args.args[1],
                    Path("output/100--test_77.txt"),
                )

    def test_summary_lists_paid_chapters(self):
        stats = DownloadStatistics(
            chapters=2, images=0, original_image_bytes=0,
            embedded_image_bytes=0, epub_bytes=150, skipped_paid_chapters=(
                "1/49 — Бицепс (2)", "1/50 — Бицепс (3)"),
        )
        with patch("builtins.print") as output:
            _print_summary(stats)
        lines = [call.args[0] for call in output.call_args_list]
        self.assertIn("  Skipped paid chapters: 2", lines)
        self.assertIn("    - 1/49 — Бицепс (2)", lines)
        self.assertIn("    - 1/50 — Бицепс (3)", lines)


if __name__ == "__main__":
    unittest.main()
