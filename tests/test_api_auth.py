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
