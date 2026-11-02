"""HTTP client for the MangaLib API."""
from __future__ import annotations

import httpx


class MangaLibClient:
    BASE_URL = "https://api.imglib.info/api"

    def __init__(self, token: str | None = None, *, timeout: float = 30):
        headers = {
            "Site-Id": "1",
            "Accept": "application/json",
            "Origin": "https://mangalib.me",
            "Referer": "https://mangalib.me/",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"
            ),
        }
        if token:
            headers["Authorization"] = f"Bearer {token.removeprefix('Bearer ').strip()}"
        self._client = httpx.Client(base_url=self.BASE_URL, headers=headers, timeout=timeout)

    def get(self, path: str, params=None) -> dict:
        response = self._client.get(path, params=params)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or "data" not in payload:
            raise ValueError("Unexpected MangaLib API response")
        return payload

    def get_current_user(self) -> dict:
        return self.get("/auth/me")["data"]

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
