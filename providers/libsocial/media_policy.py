"""RanobeLib-specific image URL trust policy and request configuration."""
from __future__ import annotations

from urllib.parse import urlsplit

HOSTS = ("ranobelib.me", "img3.mixlib.me")
PATH_PREFIX = "/uploads/ranobe/"
IMAGE_HEADERS = {
    "Referer": "https://ranobelib.me/",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/156 Safari/537.36",
    "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
}


def attachment_path(path: str) -> str:
    parsed = urlsplit(path)
    if (parsed.scheme or parsed.netloc or not parsed.path.startswith(PATH_PREFIX)
            or parsed.path != path or ".." in parsed.path.split("/")
            or "\\" in path or parsed.query or parsed.fragment):
        raise ValueError("Invalid attachment path")
    return path


def html_image_path(src: str) -> str:
    parsed = urlsplit(src.strip())
    if parsed.scheme:
        if (parsed.scheme != "https" or parsed.hostname not in HOSTS
                or parsed.port is not None or parsed.username or parsed.password):
            raise ValueError("Untrusted HTML image URL")
    elif parsed.netloc:
        raise ValueError("Protocol-relative HTML image URL is not allowed")
    if parsed.query or parsed.fragment or not parsed.path.startswith(PATH_PREFIX):
        raise ValueError("Unsupported HTML image path")
    if ".." in parsed.path.split("/") or "\\" in parsed.path:
        raise ValueError("Unsafe HTML image path")
    return parsed.path


def image_urls(path: str):
    attachment_path(path)
    return tuple("https://" + host + path for host in HOSTS)
