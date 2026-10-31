"""End-to-end RanobeLib downloader, independent of CLI and token storage."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import time

from core.download.checkpoint import ChapterCheckpoint
from core.download.retry import with_retries
from core.download.images import load_images
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
                 delay: float = 1.0, retries: int = 5,
                 status: Callable[[str], None] | None = None,
                 image_mode: str = 'original', image_quality: int = 85,
                 image_max_width: int = 1600) -> Path:
        if image_mode not in ('original', 'optimized') or not 1 <= image_quality <= 100 or image_max_width < 1:
            raise ValueError('Invalid image optimization settings')
        if delay < 0 or retries < 1:
            raise ValueError('delay must be non-negative and retries must be positive')
        if limit is not None and limit < 1:
            raise ValueError('limit must be positive')
        if status:
            status('Fetching title metadata...')
        title = self.titles.get_title(reference)
        if status:
            status('Fetching chapter index...')
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

        if status:
            status(f'Selected {len(selected)} chapters; branch={branch_id}')
        rendered = []
        checkpoints = ChapterCheckpoint(cache_dir, title.id, branch_id)
        image_cache = Path(cache_dir) / str(title.id) / f"branch-{branch_id if branch_id is not None else 'default'}"
        for index, item in enumerate(selected, 1):
            if status:
                status(f'[{index}/{len(selected)}] Loading chapter {item.volume}/{item.number}...')
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
            media = load_images(content, data.get('attachments'), image_cache,
                                int(data.get('id') or item.id), status=status,
                                image_mode=image_mode, image_quality=image_quality,
                                image_max_width=image_max_width) if isinstance(content, dict) else {}
            paths = {uid: image[0] for uid, image in media.items()}
            rendered.append(EpubChapter(
                label, chapter_to_xhtml(label, content, images=paths),
                images=tuple(media.values()),
            ))
            if progress is not None:
                progress(index, len(selected), label)

        if status:
            status('Building EPUB...')
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
