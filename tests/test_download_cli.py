"""CLI output filename and paid chapter reporting tests."""
import argparse
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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
            ), patch("interfaces.cli.download.BookDownloader") as downloader:
                downloader.return_value.prepare.return_value = plan
                downloader.return_value.download.return_value = Path("output/100--test_77.txt")
                execute(args)
                self.assertEqual(
                    downloader.return_value.download.call_args.args[1],
                    Path("output/100--test_77.txt"),
                )

    def test_chapter_range_flags_forwarded(self):
        parser = argparse.ArgumentParser()
        configure_parser(parser)
        args = parser.parse_args([
            "100--test", "--branch", "77", "--format", "txt",
            "--from", "13.4", "--to", "45", "--limit", "5",
        ])
        plan = SimpleNamespace(title=SimpleNamespace(
            id=100, slug_url="100--test", title="Book"), translations=())
        with patch("interfaces.cli.download.LibSocialClient"), patch(
            "interfaces.cli.download.KeyringTokenStorage"
        ), patch("interfaces.cli.download.BookDownloader") as downloader:
            downloader.return_value.prepare.return_value = plan
            downloader.return_value.download.return_value = Path("book.txt")
            execute(args)
            kwargs = downloader.return_value.download.call_args.kwargs
            self.assertEqual(kwargs["chapter_from"], "13.4")
            self.assertEqual(kwargs["chapter_to"], "45")
            self.assertEqual(kwargs["limit"], 5)

    def test_list_chapters_does_not_download(self):
        parser = argparse.ArgumentParser()
        configure_parser(parser)
        args = parser.parse_args(["100--test", "--branch", "77", "--list-chapters"])
        chapters = (
            SimpleNamespace(volume="1", number="45", name="Last",
                            branches=(SimpleNamespace(branch_id=77),), index=None),
            SimpleNamespace(volume="1", number="13.4", name="First",
                            branches=(SimpleNamespace(branch_id=77),), index=None),
            SimpleNamespace(volume="1", number="2", name="Other",
                            branches=(SimpleNamespace(branch_id=8),), index=None),
        )
        plan = SimpleNamespace(title=SimpleNamespace(
            id=100, slug_url="100--test", title="Book"),
            translations=(), chapters=chapters)
        with patch("interfaces.cli.download.LibSocialClient"), patch(
            "interfaces.cli.download.KeyringTokenStorage"
        ), patch("interfaces.cli.download.BookDownloader") as downloader, patch(
            "builtins.print"
        ) as printed:
            downloader.return_value.prepare.return_value = plan
            execute(args)
            downloader.return_value.download.assert_not_called()
            lines = [call.args[0] for call in printed.call_args_list]
            self.assertIn("1/13.4 — First", lines)
            self.assertIn("1/45 — Last", lines)
            self.assertNotIn("1/2 — Other", lines)
            self.assertLess(lines.index("1/13.4 — First"), lines.index("1/45 — Last"))

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
