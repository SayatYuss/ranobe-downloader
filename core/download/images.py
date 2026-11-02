"""Resolve chapter attachments, download images, and cache them for EPUB export."""
from __future__ import annotations

import os
from hashlib import sha256
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

import httpx

from core.download.image_optimization import optimize_image

FORMATS = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
           "gif": "image/gif", "webp": "image/webp"}
SIGNATURES = {
    "image/jpeg": lambda b: b.startswith(bytes.fromhex("ffd8ff")),
    "image/png": lambda b: b.startswith(bytes.fromhex("89504e470d0a1a0a")),
    "image/gif": lambda b: b.startswith((b"GIF87a", b"GIF89a")),
    "image/webp": lambda b: len(b) > 12 and b[:4] == b"RIFF" and b[8:12] == b"WEBP",
}
MIME_EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png",
                   "image/gif": "gif", "image/webp": "webp"}
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


def detect_image_format(data: bytes) -> tuple[str, str]:
    """Return the actual MIME type and extension based on image bytes."""
    if data:
        for mime, matches in SIGNATURES.items():
            if matches(data):
                return mime, MIME_EXTENSIONS[mime]
    raise ValueError("Unsupported or invalid image data")


def _verified_media(data, mime):
    if not data or mime not in SIGNATURES or not SIGNATURES[mime](data):
        raise ValueError(f"Invalid {mime} image data")


def _fetch(url):
    """Compatibility hook for callers mocking the original image downloader."""
    from providers.libsocial.media import fetch_image_url
    return fetch_image_url(url)


def _legacy_media(attachment):
    """Retain old direct load_images calls without coupling normal provider injection."""
    from providers.libsocial.media_policy import attachment_path, image_urls

    path = str(attachment.get("originalUrl") or attachment.get("url") or "")
    attachment_path(path)
    failures = []
    for url in image_urls(path):
        try:
            return _fetch(url)
        except (httpx.HTTPError, ValueError) as exc:
            failures.append(f"{url}: {exc}")
    raise ValueError("Failed to download image: " + "; ".join(failures))


def load_images(document, attachments, cache_directory: Path, chapter_id: int, status=None,
                image_mode='original', image_quality=85, image_max_width=1600,
                image_stats=None, fetch_media=None, validate_attachment=None):
    """Return UUID -> (EPUB path, bytes, mime), using detected image formats."""
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
        path = str(attachment.get("originalUrl") or attachment.get("url") or "")
        if validate_attachment is None:
            from providers.libsocial.media_policy import attachment_path
            attachment_path(path)
        else:
            validate_attachment(path)
        if not valid_image_identifier(uid):
            raise ValueError("Invalid image identifier")

        # Keep the API extension for locating older cache entries. The real format
        # is detected from bytes, since CDNs may return JPEG for a .png URL.
        target = cache_directory / "images" / str(chapter_id) / f"{uid}.{ext}"
        data = target.read_bytes() if target.is_file() else None
        digest_path = target.with_suffix(target.suffix + ".sha256")
        if data is not None:
            try:
                detect_image_format(data)
                if digest_path.is_file() and (
                    digest_path.read_text(encoding="ascii").strip()
                    != sha256(data).hexdigest()
                ):
                    data = None
            except (ValueError, UnicodeError, OSError):
                data = None

        if data is None:
            if status:
                status(f'  Downloading image {uid}.{ext}...')
            data = (fetch_media or _legacy_media)(attachment)
            detect_image_format(data)
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = None
            try:
                with NamedTemporaryFile(dir=target.parent, delete=False) as handle:
                    temp = Path(handle.name)
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp, target)
                checksum_temp = None
                try:
                    with NamedTemporaryFile(mode="w", encoding="ascii",
                                            dir=target.parent, delete=False) as handle:
                        checksum_temp = Path(handle.name)
                        handle.write(sha256(data).hexdigest())
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(checksum_temp, digest_path)
                finally:
                    if checksum_temp is not None:
                        checksum_temp.unlink(missing_ok=True)
            finally:
                if temp is not None:
                    temp.unlink(missing_ok=True)

        original_size = len(data)
        mime, output_ext = detect_image_format(data)
        if image_mode == 'optimized':
            data, mime, output_ext = optimize_image(
                data, mime, quality=image_quality, max_width=image_max_width)
        result[uid] = (f"images/{chapter_id}-{uid}.{output_ext}", data, mime)
        if image_stats is not None:
            image_stats(original_size, len(data))
    return result
