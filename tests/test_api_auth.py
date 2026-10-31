import unittest
from unittest.mock import patch, MagicMock
import httpx

from providers.libsocial.client import LibSocialClient
from interfaces.cli import auth


class ApiAuthTests(unittest.TestCase):
    def test_site_headers_and_bearer(self):
        with LibSocialClient("example-token") as client:
            headers = client._client.headers
            self.assertEqual(headers["Referer"], "https://ranobelib.me/")
            self.assertEqual(headers["Origin"], "https://ranobelib.me")
            self.assertEqual(headers["Site-Id"], "3")
            self.assertEqual(headers["Authorization"], "Bearer example-token")

    def test_preformatted_token_not_double_prefixed(self):
        with LibSocialClient("Bearer example-token") as client:
            self.assertEqual(client._client.headers["Authorization"], "Bearer example-token")

    def test_login_403_keeps_storage_unchanged(self):
        request = httpx.Request("GET", "https://api.imglib.info/api/auth/me")
        response = httpx.Response(403, request=request)
        error = httpx.HTTPStatusError("forbidden", request=request, response=response)
        with patch.object(auth.getpass, "getpass", return_value="test-token"), patch.object(
            auth, "LibSocialClient"
        ) as cls, patch.object(auth.storage, "save") as save, patch("builtins.print") as output:
            cls.return_value.__enter__.return_value.get_current_user.side_effect = error
            auth.login()
            save.assert_not_called()
            self.assertIn("403", output.call_args.args[0])

    def test_login_accepts_bearer_prefix(self):
        with patch.object(auth.getpass, "getpass", return_value="Bearer test-token"), patch.object(
            auth, "LibSocialClient"
        ) as cls, patch.object(auth.storage, "save") as save, patch("builtins.print"):
            cls.return_value.__enter__.return_value.get_current_user.return_value = {"username": "test"}
            auth.login()
            cls.assert_called_once_with("test-token")
            save.assert_called_once_with("test-token")

    def test_status_403_has_message(self):
        request = httpx.Request("GET", "https://api.imglib.info/api/auth/me")
        response = httpx.Response(403, request=request)
        error = httpx.HTTPStatusError("forbidden", request=request, response=response)
        with patch.object(auth.storage, "load", return_value="test-token"), patch.object(
            auth, "LibSocialClient"
        ) as cls, patch("builtins.print") as output:
            cls.return_value.__enter__.return_value.get_current_user.side_effect = error
            auth.status()
            self.assertIn("403", output.call_args.args[0])

    def test_audit_resume_without_json(self):
        import argparse
        from pathlib import Path
        from interfaces.cli.audit import configure_parser, execute
        parser = argparse.ArgumentParser()
        configure_parser(parser)
        args = parser.parse_args(["271947--test", "--resume"])
        self.assertIsNone(args.json)
        with patch("interfaces.cli.audit.LibSocialClient") as client, patch(
            "interfaces.cli.audit.TitleProvider"
        ) as title, patch("interfaces.cli.audit.ChapterProvider") as chapters, patch(
            "interfaces.cli.audit.audit_title"
        ) as audit, patch("interfaces.cli.audit.Path.is_file", return_value=False):
            title.return_value.get_title.return_value = MagicMock(
                slug_url="271947--test", title="Test")
            chapters.return_value.get_chapters.return_value = []
            audit.return_value = {"title": "Test", "slug_url": "271947--test",
                                  "selected_branch": None, "status": "COMPATIBLE",
                                  "chapters_total": 0, "sampled": 0, "passed": 0,
                                  "failed": 0, "unverified": 0,
                                  "available_branches": [], "node_types": {},
                                  "issues": []}
            with __import__("tempfile").TemporaryDirectory() as directory:
                args.output_dir = Path(directory)
                execute(args)
            audit.assert_called_once()
