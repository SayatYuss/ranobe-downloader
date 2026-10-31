"""Resolve legacy HTML image URLs to trusted chapter attachments."""
from __future__ import annotations

from html.parser import HTMLParser
import re
from urllib.parse import urlsplit

from core.download.images import HOSTS, FORMATS


def _image_path(src: str) -> str:
    parsed = urlsplit(src.strip())
    if parsed.scheme:
        if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.port is not None:
            raise ValueError("Untrusted HTML image URL")
    elif parsed.netloc:
        raise ValueError("Protocol-relative HTML image URL is not allowed")
    if parsed.query or parsed.fragment or not parsed.path.startswith("/uploads/ranobe/"):
        raise ValueError("Unsupported HTML image path")
    if ".." in parsed.path.split("/") or "\\" in parsed.path:
        raise ValueError("Unsafe HTML image path")
    return parsed.path


class _ImageCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sources = []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            src = dict(attrs).get("src")
            if not src:
                raise ValueError("HTML image missing src")
            self.sources.append(src)

    handle_startendtag = handle_starttag


def html_image_sources(html: str) -> list[str]:
    parser = _ImageCollector()
    parser.feed(html)
    return list(dict.fromkeys(parser.sources))


def resolve_html_images(html: str, attachments) -> tuple[dict[str, str], list[str]]:
    """Return original src -> attachment UUID and UUIDs in first-appearance order."""
    sources = html_image_sources(html)
    if not sources:
        return {}, []
    lookup = {}
    for attachment in attachments or []:
        if not isinstance(attachment, dict):
            continue
        uid = attachment.get("name")
        if not isinstance(uid, str) or not uid:
            continue
        for key in ("originalUrl", "url", "previewUrl"):
            value = attachment.get(key)
            if not isinstance(value, str):
                continue
            try:
                path = _image_path(value)
            except ValueError:
                continue
            lookup[path] = uid
    matched = {}
    for src in sources:
        path = _image_path(src)
        uid = lookup.get(path)
        if uid is None:
            match = re.fullmatch(
                r"/uploads/ranobe/\d+/chapters/\d+/([0-9a-fA-F-]{36})\.([A-Za-z]+)",
                path,
            )
            if match is None or match.group(2).lower() not in FORMATS:
                raise ValueError(f"HTML image attachment missing: {path}")
            uid = match.group(1)
            if not isinstance(attachments, list):
                raise ValueError("HTML attachments must be a mutable list")
            attachments.append({
                "name": uid, "extension": match.group(2).lower(),
                "originalUrl": path,
            })
            lookup[path] = uid
        matched[src] = uid
    return matched, list(dict.fromkeys(matched.values()))
