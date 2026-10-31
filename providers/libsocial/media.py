"""RanobeLib HTTP image transport, separate from the generic media cache."""
import httpx

from providers.libsocial.media_policy import IMAGE_HEADERS, image_urls

MAX_SIZE = 30 * 1024 * 1024


def fetch_image_url(url: str) -> bytes:
    with httpx.Client(timeout=25, follow_redirects=False, headers=IMAGE_HEADERS) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            if response.is_redirect:
                raise ValueError("Image redirects not allowed")
            advertised = response.headers.get("Content-Length")
            if advertised is not None and advertised.isdecimal() and int(advertised) > MAX_SIZE:
                raise ValueError(f"Image exceeds {MAX_SIZE // (1024 * 1024)} MiB")
            payload = bytearray()
            for chunk in response.iter_bytes():
                payload.extend(chunk)
                if len(payload) > MAX_SIZE:
                    raise ValueError(f"Image exceeds {MAX_SIZE // (1024 * 1024)} MiB")
            return bytes(payload)


def fetch_attachment(attachment: dict, fetch=fetch_image_url) -> bytes:
    path = str(attachment.get("originalUrl") or attachment.get("url") or "")
    errors = []
    for url in image_urls(path):
        try:
            return fetch(url)
        except (httpx.HTTPError, ValueError) as exc:
            errors.append(f"{url}: {exc}")
    raise ValueError("Failed to download image: " + "; ".join(errors))
