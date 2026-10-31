"""Stable, non-interactive Python interface for downloading books."""
from __future__ import annotations

from dataclasses import dataclass
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
        plan = self._backend.prepare(reference, status=status)
        title = plan.title
        return Book(
            title=title.title, id=title.id, slug_url=title.slug_url,
            authors=tuple(title.authors), translations=plan.translations,
            chapter_count=len(plan.chapters), _plan=plan,
        )

    def download(self, book: Book | str, *, format: ExportFormat = "epub",
                 output: str | Path | None = None, branch_id: int | None = None,
                 limit: int | None = None, resume: bool = False,
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
        if isinstance(book, str):
            book = self.get_book(book, status=status)
        if output is None:
            import re
            if not re.fullmatch(r"[A-Za-z0-9_-]+", book.slug_url):
                raise ValueError("Unsafe book slug for output filename")
            suffix = str(branch_id) if branch_id is not None else "default"
            output = Path("output") / f"{book.slug_url}_{suffix}.{format}"
        # Switch the exporter only for this invocation, restoring it even on errors.
        # This facade is synchronous; concurrent calls to one instance are unsupported.
        previous = self._backend.exporter
        try:
            self._backend.exporter = _EXPORTERS[format]()
            return self._backend.download(
                book._plan, output, branch_id=branch_id, limit=limit,
                progress=progress, resume=resume, cache_dir=cache_dir,
                delay=delay, retries=retries, status=status,
                image_mode=image_mode, image_quality=image_quality,
                image_max_width=image_max_width, statistics=statistics,
            )
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
