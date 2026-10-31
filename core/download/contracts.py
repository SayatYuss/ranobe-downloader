"""Structural interfaces for downloader data sources and EPUB output.

Adapters may implement these protocols without inheriting from core classes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, Callable

from core.chapter_content import ChapterContent


class TitleSource(Protocol):
    def get_title(self, reference: str) -> Any: ...


class ChapterIndexSource(Protocol):
    def get_chapters(self, reference: str) -> list[Any]: ...


class ChapterBodySource(Protocol):
    def get_chapter(
        self, reference: str, *, volume: str, number: str,
        branch_id: int | None = None,
    ) -> ChapterContent: ...


class BookExporter(Protocol):
    def export(
        self, destination: str | Path, *, title: str,
        authors: tuple[str, ...], chapters: list[Any],
        description: str, identifier: str,
        cover: bytes | None, cover_media_type: str | None,
    ) -> Path: ...
