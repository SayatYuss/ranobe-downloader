"""End-to-end RanobeLib downloader, independent of CLI and token storage."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable

from core.chapter_xhtml import chapter_to_xhtml
from exporters.epub import EpubChapter, EpubExporter
from providers.libsocial.chapter_content import ChapterContentProvider
from providers.libsocial.chapters import ChapterProvider
from providers.libsocial.titles import TitleProvider


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
                 progress: Callable[[int, int, str], None] | None = None) -> Path:
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
        for index, item in enumerate(selected, 1):
            raw = self.contents.get_chapter(title.slug_url, volume=item.volume,
                                            number=item.number, branch_id=branch_id)
            if not isinstance(raw.content, dict):
                raise ValueError(f'Chapter {item.volume}/{item.number}: unsupported content')
            label = raw.title or item.name or f'Глава {item.number}'
            rendered.append(EpubChapter(label, chapter_to_xhtml(label, raw.content)))
            if progress is not None:
                progress(index, len(selected), label)

        return self.exporter.export(
            output, title=title.title, authors=title.authors, chapters=rendered,
            description=title.description, identifier=f'ranobelib:{title.id}',
        )
