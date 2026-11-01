"""Public exceptions raised by the library facade."""
from __future__ import annotations

import httpx


class DownloaderError(Exception):
    """Base error for failures reported by the public downloader API."""


class AuthenticationError(DownloaderError):
    """The content provider rejected authentication or access."""


class ProviderError(DownloaderError):
    """The content provider returned an unexpected HTTP response."""


class NetworkError(DownloaderError):
    """Could not communicate with the content provider."""


def translate_http_error(error: httpx.HTTPError) -> DownloaderError:
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status in (401, 403):
            return AuthenticationError(f"Provider access denied (HTTP {status})")
        return ProviderError(f"Provider returned HTTP {status}")
    return NetworkError(f"Provider network request failed: {error}")
