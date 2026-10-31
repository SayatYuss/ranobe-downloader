"""Stable, non-interactive Python interface for downloading books."""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
import httpx
from .errors import translate_http_error
from pathlib import Path
from typing import Callable, Literal

from core.book_downloader import BookDownloader
from core.download.plan import DownloadPlan, Translation
from core.download.statistics import DownloadStatistics
from exporters.epub import EpubExporter
from exporters.text import HtmlExporter, TxtExporter
from providers.libsocial.client import LibSocialClient

ExportFormat = Literal["epub", "txt", "html"]
_EXPORTERS = {"epub": EpubExporter, "txt": TxtExporter, "html": HtmlExporter}


@dataclass(frozen=True)
class Book:
    """Prepared title with its available chapters and translation branches."""
    title: str
    id: int
    slug_url: str
    authors: tuple[str, ...]
    translations: tuple[Translation, ...]
    chapter_count: int
    _plan: DownloadPlan

    def list_chapters(self, branch_id: int | None = None) -> tuple[dict, ...]:
        """Chapter index metadata; no chapter content is downloaded."""
        from core.book_downloader import _chapter_order
        chapters = sorted((ch for ch in self._plan.chapters if branch_id is None
                           or any(b.branch_id == branch_id for b in ch.branches)),
                          key=_chapter_order)
        return tuple({"volume": str(ch.volume), "number": str(ch.number),
                      "name": ch.name} for ch in chapters)


class Downloader:
    """Create a reusable downloader, optionally with an external content backend.

    A token is optional for public works. Credential storage and console input
    belong to callers, not the library.
    """

    def __init__(self, token: str | None = None, *, client=None,
                 backend: BookDownloader | None = None):
        if backend is not None and (token is not None or client is not None):
            raise ValueError("backend cannot be combined with token or client")
        if client is not None and token is not None:
            raise ValueError("Pass either client or token")
        self._owns_client = backend is None and client is None
        self._client = (LibSocialClient(token) if self._owns_client else client)
        self._backend = backend or BookDownloader(self._client)
        self._closed = False

    def _ensure_open(self):
        if self._closed:
            raise RuntimeError("Downloader is closed")

    def get_book(self, reference: str, *,
                 status: Callable[[str], None] | None = None) -> Book:
        """Fetch metadata and the chapter index without downloading content."""
        self._ensure_open()
        if not isinstance(reference, str) or not reference.strip():
            raise ValueError("reference must be a nonempty string")
        try:
            plan = self._backend.prepare(reference, status=status)
        except httpx.HTTPError as exc:
            raise translate_http_error(exc) from exc
        title = plan.title
        return Book(
            title=title.title, id=title.id, slug_url=title.slug_url,
            authors=tuple(title.authors), translations=plan.translations,
            chapter_count=len(plan.chapters), _plan=plan,
        )

    def download(self, book: Book | str, *, format: ExportFormat = "epub",
                 output: str | Path | None = None, branch_id: int | None = None,
                 limit: int | None = None,
                 chapter_from: str | int | None = None,
                 chapter_to: str | int | None = None,
                 resume: bool = False,
                 cache_dir: str | Path = "output/.cache", delay: float = 1.0,
                 retries: int = 5, image_mode: str = "original",
                 image_quality: int = 85, image_max_width: int = 1600,
                 progress: Callable[[int, int, str], None] | None = None,
                 status: Callable[[str], None] | None = None,
                 statistics: Callable[[DownloadStatistics], None] | None = None) -> Path:
        """Download an already prepared Book or resolve a reference and export it."""
        self._ensure_open()
        if format not in _EXPORTERS:
            raise ValueError("format must be epub, txt or html")
        if not isinstance(book, (Book, str)):
            raise TypeError("book must be Book or a reference string")
        if limit is not None and (type(limit) is not int or limit < 1):
            raise ValueError("limit must be a positive integer")
        if branch_id is not None and type(branch_id) is not int:
            raise TypeError("branch_id must be an integer")
        if not isinstance(delay, (float, int)) or not math.isfinite(delay) or delay < 0:
            raise ValueError("delay must be a finite non-negative number")
        if type(retries) is not int or retries < 1:
            raise ValueError("retries must be a positive integer")
        if image_mode not in ("original", "optimized"):
            raise ValueError("image_mode must be original or optimized")
        if type(image_quality) is not int or not 1 <= image_quality <= 100:
            raise ValueError("image_quality must be between 1 and 100")
        if type(image_max_width) is not int or image_max_width < 1:
            raise ValueError("image_max_width must be a positive integer")
        if isinstance(book, str):
            book = self.get_book(book, status=status)
        if output is None:
            if not re.fullmatch(r"[A-Za-z0-9_-]+", book.slug_url):
                raise ValueError("Unsafe book slug for output filename")
            suffix = str(branch_id) if branch_id is not None else "default"
            output = Path("output") / f"{book.slug_url}_{suffix}.{format}"
        # Switch the exporter only for this invocation, restoring it even on errors.
        # This facade is synchronous; concurrent calls to one instance are unsupported.
        previous = self._backend.exporter
        try:
            self._backend.exporter = _EXPORTERS[format]()
            try:
                return self._backend.download(
                book._plan, output, branch_id=branch_id, limit=limit,
                chapter_from=chapter_from, chapter_to=chapter_to,
                progress=progress, resume=resume, cache_dir=cache_dir,
                delay=delay, retries=retries, status=status,
                image_mode=image_mode, image_quality=image_quality,
                image_max_width=image_max_width, statistics=statistics,
                )
            except httpx.HTTPError as exc:
                raise translate_http_error(exc) from exc
        finally:
            self._backend.exporter = previous

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            if self._owns_client:
                self._client.close()

    def __enter__(self) -> Downloader:
        self._ensure_open()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
