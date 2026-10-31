"""Download cover artwork from the trusted RanobeLib image host."""
from __future__ import annotations

from urllib.parse import urlsplit

import httpx


def download_cover(url: str) -> tuple[bytes, str]:
    address = urlsplit(url)
    if address.scheme != "https" or address.hostname != "cover.imglib.info" or address.username or address.password or address.port not in (None, 443):
        raise ValueError("Cover URL must use the trusted HTTPS image host")
    if not address.path.startswith("/uploads/"):
        raise ValueError("Unexpected cover path")
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            if response.is_redirect:
                raise ValueError("Cover redirects are not allowed")
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > 10 * 1024 * 1024:
                    raise ValueError("Cover exceeds 10 MiB")
    data = bytes(content)
    if data.startswith(b"\xff\xd8\xff"):
        return data, "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return data, "image/png"
    raise ValueError("Unsupported cover image format")
