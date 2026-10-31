import unittest
from unittest.mock import patch

from providers.libsocial.cover import download_cover


class FakeResponse:
    is_redirect = False

    def __init__(self):
        self.checked = False

    def raise_for_status(self):
        self.checked = True

    def iter_bytes(self):
        yield b"\xff\xd8\xffsample"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeClient:
    def __init__(self, **kwargs):
        self.headers = kwargs["headers"]
        self.response = FakeResponse()

    def stream(self, method, url):
        assert method == "GET"
        assert url.startswith("https://cover.imglib.info/uploads/")
        return self.response

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class CoverTests(unittest.TestCase):
    def test_browser_headers_and_jpeg(self):
        clients = []

        def make_client(**kwargs):
            client = FakeClient(**kwargs)
            clients.append(client)
            return client

        with patch("providers.libsocial.cover.httpx.Client", side_effect=make_client):
            image, media_type = download_cover(
                "https://cover.imglib.info/uploads/cover/book/cover/example.jpg"
            )
        self.assertEqual(media_type, "image/jpeg")
        self.assertTrue(image.startswith(b"\xff\xd8\xff"))
        headers = clients[0].headers
        self.assertEqual(headers["Referer"], "https://ranobelib.me/")
        self.assertIn("Mozilla/5.0", headers["User-Agent"])
        self.assertIn("image/", headers["Accept"])

    def test_external_host_rejected(self):
        with self.assertRaises(ValueError):
            download_cover("https://example.com/uploads/cover.jpg")
