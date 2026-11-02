"""MangaLib title reference parsing and validation."""
from urllib.parse import urlparse

ALLOWED_HOSTS = {"mangalib.me", "www.mangalib.me", "api.imglib.info"}


def parse_title_reference(reference: str) -> str:
    value = reference.strip()
    if not value:
        raise ValueError("Title reference cannot be empty")
    if "://" in value:
        url = urlparse(value)
        if url.scheme != "https" or url.hostname not in ALLOWED_HOSTS:
            raise ValueError("Only HTTPS MangaLib title URLs are accepted")
        parts = [part for part in url.path.split("/") if part]
        if "manga" not in parts:
            raise ValueError("MangaLib URL must contain /manga/")
        index = parts.index("manga")
        if index + 1 >= len(parts):
            raise ValueError("Missing manga in URL")
        value = parts[index + 1]
    if value.isdigit():
        return value
    if "--" not in value or not value.split("--", 1)[0].isdigit():
        raise ValueError("Expected a numeric manga ID or ID--slug")
    if any(char in value for char in "/?#"):
        raise ValueError("Invalid manga reference")
    return value


def is_mangalib_reference(reference: str) -> bool:
    try:
        value = reference.strip()
        if "://" not in value:
            return False
        url = urlparse(value)
        return url.scheme == "https" and url.hostname in ALLOWED_HOSTS and "manga" in url.path.split("/")
    except (AttributeError, ValueError):
        return False
