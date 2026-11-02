"""MangaLib image transport with strict CDN host validation."""
from urllib.parse import urlsplit
import httpx

from core.download.images import MAX_SIZE


def _validated_url(attachment: dict) -> str:
    url = str(attachment.get("originalUrl") or "")
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname != "img3.cdnlibs.org"
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or parsed.query or parsed.fragment):
        raise ValueError("Untrusted MangaLib image URL")
    return url


def fetch_image(attachment: dict) -> bytes:
    url = _validated_url(attachment)
    headers = {
        "Referer": "https://mangalib.me/",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/156 Safari/537.36",
        "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
    }
    with httpx.Client(timeout=25, follow_redirects=False, headers=headers) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            if response.is_redirect:
                raise ValueError("MangaLib image redirects are not allowed")
            advertised = response.headers.get("Content-Length")
            if advertised and advertised.isdecimal() and int(advertised) > MAX_SIZE:
                raise ValueError("MangaLib image exceeds 30 MiB")
            payload = bytearray()
            for chunk in response.iter_bytes():
                payload.extend(chunk)
                if len(payload) > MAX_SIZE:
                    raise ValueError("MangaLib image exceeds 30 MiB")
            return bytes(payload)


def download_cover(url: str) -> tuple[bytes, str]:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname != "cover.imglib.info"
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or not parsed.path.startswith("/uploads/") or parsed.query or parsed.fragment):
        raise ValueError("Untrusted MangaLib cover URL")
    headers = {"Referer": "https://mangalib.me/", "User-Agent": "Mozilla/5.0"}
    with httpx.Client(timeout=20, follow_redirects=False, headers=headers) as client:
        response = client.get(url)
        response.raise_for_status()
        if response.is_redirect or len(response.content) > 10 * 1024 * 1024:
            raise ValueError("Invalid MangaLib cover response")
        data = response.content
    if data.startswith(bytes.fromhex("ffd8ff")):
        return data, "image/jpeg"
    if data.startswith(bytes.fromhex("89504e470d0a1a0a")):
        return data, "image/png"
    if len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return data, "image/webp"
    raise ValueError("Unsupported MangaLib cover image format")
