"""Resolve legacy HTML image URLs to trusted chapter attachments."""
from __future__ import annotations

from html.parser import HTMLParser
from hashlib import sha256
import re
from providers.libsocial.media_policy import html_image_path


# Compatibility alias; policy is maintained by the RanobeLib provider.
_image_path = html_image_path

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
                r"/uploads/ranobe/([A-Za-z0-9_-]+)/chapters/([0-9]+)/([A-Za-z0-9_.-]+)\.(jpg|jpeg|png|gif|webp)",
                path, flags=re.IGNORECASE,
            )
            if match is None:
                raise ValueError(f"HTML image attachment missing: {path}")
            # A stable hex ID is compatible with the shared image cache and EPUB exporter.
            # Preserve the original path; never build the fetch URL from this identifier.
            uid = sha256(path.encode("utf-8")).hexdigest()
            if not isinstance(attachments, list):
                raise ValueError("HTML attachments must be a mutable list")
            attachments.append({
                "name": uid, "extension": match.group(4).lower(),
                "originalUrl": path,
            })
            lookup[path] = uid
        matched[src] = uid
    return matched, list(dict.fromkeys(matched.values()))
