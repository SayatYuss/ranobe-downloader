"""End-to-end RanobeLib downloader, independent of CLI and token storage."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import time

from core.download.checkpoint import ChapterCheckpoint
from core.download.retry import with_retries
from pathlib import Path
from typing import Callable

from core.chapter_xhtml import chapter_to_xhtml
from exporters.epub import EpubChapter, EpubExporter
from providers.libsocial.chapter_content import ChapterContentProvider
from providers.libsocial.chapters import ChapterProvider
from providers.libsocial.titles import TitleProvider
from providers.libsocial.cover import download_cover
import httpx


def _chapter_order(chapter):
    def decimal_key(value):
        try:
            return (0, Decimal(str(value)))
        except (InvalidOperation, ValueError):
            return (1, str(value))
    return (decimal_key(chapter.volume), decimal_key(chapter.number), chapter.index or 0)


class BookDownloader:
    def __init__(self, client, exporter=None):
        self.titles = TitleProvider(client)
        self.chapters = ChapterProvider(client)
        self.contents = ChapterContentProvider(client)
        self.exporter = exporter or EpubExporter()

    def download(self, reference: str, output: str | Path, *,
                 branch_id: int | None = None, limit: int | None = None,
                 progress: Callable[[int, int, str], None] | None = None,
                 resume: bool = False, cache_dir: str | Path = 'output/.cache',
                 delay: float = 1.0, retries: int = 5) -> Path:
        if delay < 0 or retries < 1:
            raise ValueError('delay must be non-negative and retries must be positive')
        if limit is not None and limit < 1:
            raise ValueError('limit must be positive')
        title = self.titles.get_title(reference)
        chapter_list = self.chapters.get_chapters(title.slug_url)
        if not chapter_list:
            raise ValueError('No chapters found')

        available = {b.branch_id for chapter in chapter_list for b in chapter.branches
                     if b.branch_id is not None}
        if branch_id is None:
            if len(available) > 1:
                raise ValueError('Multiple translations available. Specify --branch: '
                                 + ', '.join(str(v) for v in sorted(available)))
            branch_id = next(iter(available), None)
        elif available and branch_id not in available:
            raise ValueError(f'Translation branch {branch_id} is not available')

        selected = [chapter for chapter in chapter_list
                    if branch_id is None or any(b.branch_id == branch_id for b in chapter.branches)]
        selected.sort(key=_chapter_order)
        if limit is not None:
            selected = selected[:limit]
        if not selected:
            raise ValueError('No chapters in selected translation branch')

        rendered = []
        checkpoints = ChapterCheckpoint(cache_dir, title.id, branch_id)
        for index, item in enumerate(selected, 1):
            data = checkpoints.load(item.id, volume=item.volume, number=item.number) if resume else None
            if data is None:
                raw = with_retries(
                    lambda: self.contents.get_chapter(
                        title.slug_url, volume=item.volume,
                        number=item.number, branch_id=branch_id),
                    attempts=retries,
                )
                data = raw.data
                if not isinstance(raw.content, (dict, str)):
                    raise ValueError(f'Chapter {item.volume}/{item.number}: unsupported content')
                checkpoints.save(item.id, data, volume=item.volume, number=item.number)
                if delay > 0 and index < len(selected):
                    time.sleep(delay)
            content = data.get('content')
            if not isinstance(content, (dict, str)):
                raise ValueError(f'Chapter {item.volume}/{item.number}: unsupported content')
            label = data.get('name') or item.name or f'Глава {item.number}'
            rendered.append(EpubChapter(label, chapter_to_xhtml(label, content)))
            if progress is not None:
                progress(index, len(selected), label)

        cover = None
        cover_type = None
        cover_url = getattr(title, 'cover_url', None)
        if cover_url:
            try:
                cover, cover_type = download_cover(cover_url)
            except (httpx.HTTPError, ValueError) as exc:
                print(f'Cover skipped: {exc}')

        return self.exporter.export(
            output, title=title.title, authors=title.authors, chapters=rendered,
            description=title.description, identifier=f'ranobelib:{title.id}',
            cover=cover, cover_media_type=cover_type,
        )
