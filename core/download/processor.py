"""Prepare chapter XHTML and local media references for EPUB export."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from core.chapter_content import ChapterContent, ChapterContentUnavailable
from core.chapter_xhtml import chapter_to_xhtml
from core.download.html_images import resolve_html_images
from core.download.images import load_images
from core.download.models import NormalizedChapter


class ContentProcessor:
    def __init__(self, media=None):
        self.media = media

    def process(self, data: dict, item, image_cache: str | Path, *,
                status: Callable[[str], None] | None = None,
                image_mode: str = "original", image_quality: int = 85,
                image_max_width: int = 1600,
                image_stats: Callable[[int, int], None] | None = None,
                skip_images: bool = False) -> NormalizedChapter:
        reason = ChapterContent.from_api(data).unavailable_reason
        if reason:
            raise ChapterContentUnavailable(f"Chapter {item.volume}/{item.number}: {reason}")
        content = data.get("content")
        if not isinstance(content, (dict, str)):
            raise ValueError(f"Chapter {item.volume}/{item.number}: unsupported content")
        label = data.get("name") or item.name or f"Глава {item.number}"
        attachments = list(data.get("attachments") or [])
        resolve = self.media.resolve_html_images if self.media is not None else resolve_html_images
        load = self.media.load_images if self.media is not None else load_images
        html_sources = {}
        if isinstance(content, str):
            html_sources, uids = resolve(content, attachments)
            image_document = {"type": "doc", "content": [
                {"type": "image", "attrs": {"images": [{"image": uid}]}}
                for uid in uids
            ]}
        else:
            image_document = content
        if skip_images:
            from core.download.images import image_refs
            paths = {uid: f"images/{uid}" for uid in image_refs(image_document)}
            media = {}
        else:
            media = load(
                image_document, attachments, Path(image_cache),
                int(data.get("id") or item.id), status=status,
                image_mode=image_mode, image_quality=image_quality,
                image_max_width=image_max_width, image_stats=image_stats,
            )
            paths = {uid: image[0] for uid, image in media.items()}
        html_paths = {src: paths[uid] for src, uid in html_sources.items()}
        return NormalizedChapter(
            label, chapter_to_xhtml(label, content, images=paths, html_images=html_paths),
            images=tuple(media.values()),
        )
