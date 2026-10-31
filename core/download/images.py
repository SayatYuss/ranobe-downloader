"""Resolve chapter attachments, download images, and cache them for EPUB export."""
from __future__ import annotations

import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from providers.libsocial.media_policy import HOSTS, IMAGE_HEADERS, attachment_path, image_urls
import httpx
from core.download.image_optimization import optimize_image

FORMATS = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
           "gif": "image/gif", "webp": "image/webp"}
SIGNATURES = {"image/jpeg": lambda b: b.startswith(bytes.fromhex("ffd8ff")),
              "image/png": lambda b: b.startswith(bytes.fromhex("89504e470d0a1a0a")),
              "image/gif": lambda b: b.startswith((b"GIF87a", b"GIF89a")),
              "image/webp": lambda b: len(b) > 12 and b[:4] == b"RIFF" and b[8:12] == b"WEBP"}
MAX_SIZE = 30 * 1024 * 1024
IMAGE_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,128}")


def valid_image_identifier(uid: str) -> bool:
    """Allow API-provided IDs while preventing path traversal and unsafe filenames."""
    return isinstance(uid, str) and IMAGE_ID_PATTERN.fullmatch(uid) is not None


def image_refs(document):
    """Return image UUIDs in appearance order; reject unsupported shapes."""
    found = []
    def visit(node):
        if not isinstance(node, dict):
            return
        if node.get("type") == "image":
            images = (node.get("attrs") or {}).get("images") or []
            if not images:
                raise ValueError("Image node has no images")
            for item in images:
                uid = item.get("image") if isinstance(item, dict) else None
                if not isinstance(uid, str) or not uid:
                    raise ValueError("Image node has invalid UUID")
                found.append(uid)
        for child in node.get("content") or []:
            visit(child)
    visit(document)
    return list(dict.fromkeys(found))


def _verified_media(data, mime):
    if not data or not SIGNATURES[mime](data):
        raise ValueError(f"Invalid {mime} image data")


def _fetch(url):
    headers = IMAGE_HEADERS
    with httpx.Client(timeout=25, follow_redirects=False, headers=headers) as client:
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


def load_images(document, attachments, cache_directory: Path, chapter_id: int, status=None,
                image_mode='original', image_quality=85, image_max_width=1600,
                image_stats=None):
    """Return UUID -> (EPUB path, bytes, mime). Download referenced attachments only."""
    if image_mode not in ('original', 'optimized'):
        raise ValueError('image_mode must be original or optimized')
    refs = image_refs(document)
    if not refs:
        return {}
    by_name = {a.get("name"): a for a in attachments or []
               if isinstance(a, dict) and isinstance(a.get("name"), str)}
    result = {}
    for uid in refs:
        attachment = by_name.get(uid)
        if attachment is None:
            raise ValueError(f"Image attachment missing: {uid}")
        ext = str(attachment.get("extension") or "").lower().lstrip(".")
        if ext not in FORMATS:
            raise ValueError(f"Unsupported image extension: {ext}")
        mime = FORMATS[ext]
        path = str(attachment.get("originalUrl") or attachment.get("url") or "")
        attachment_path(path)
        filename = f"{uid}.{ext}"
        if not valid_image_identifier(uid):
            raise ValueError("Invalid image identifier")
        target = cache_directory / "images" / str(chapter_id) / filename
        data = target.read_bytes() if target.is_file() else None
        if data is not None:
            try:
                _verified_media(data, mime)
            except ValueError:
                data = None
        if data is None:
            if status:
                status(f'  Downloading image {uid}.{ext}...')
            failures = []
            for url in image_urls(path):
                try:
                    data = _fetch(url)
                    _verified_media(data, mime)
                    break
                except (httpx.HTTPError, ValueError) as exc:
                    failures.append(f"{url}: {exc}")
            else:
                raise ValueError(f"Failed to download image {uid}: {'; '.join(failures)}")
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = None
            try:
                with NamedTemporaryFile(dir=target.parent, delete=False) as handle:
                    temp = Path(handle.name)
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp, target)
            finally:
                if temp is not None:
                    temp.unlink(missing_ok=True)
        original_size = len(data)
        output_ext = ext
        if image_mode == 'optimized':
            data, mime, output_ext = optimize_image(
                data, mime, quality=image_quality, max_width=image_max_width)
        result[uid] = (f"images/{chapter_id}-{uid}.{output_ext}", data, mime)
        if image_stats is not None:
            image_stats(original_size, len(data))
    return result
