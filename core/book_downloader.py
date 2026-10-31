"""End-to-end RanobeLib downloader, independent of CLI and token storage."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import time

from core.download.checkpoint import ChapterCheckpoint
from core.download.fetcher import ChapterFetcher
from core.download.processor import ContentProcessor
from core.download.statistics import DownloadStatistics
from core.download.plan import DownloadPlan, make_translations
from pathlib import Path
from typing import Callable

from exporters.epub import EpubExporter
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
    def __init__(self, client=None, exporter=None, *,
                 titles=None, chapters=None, contents=None):
        """Inject any compatible content sources, or use the RanobeLib defaults.

        Existing BookDownloader(client, exporter) calls remain supported.
        No CLI, credential store, or interactive input is required here.
        """
        if client is None and any(source is None for source in (titles, chapters, contents)):
            raise ValueError("A client or all three content sources are required")
        self.titles = titles if titles is not None else TitleProvider(client)
        self.chapters = chapters if chapters is not None else ChapterProvider(client)
        self.contents = contents if contents is not None else ChapterContentProvider(client)
        self.exporter = exporter if exporter is not None else EpubExporter()

    def prepare(self, reference: str, *,
                status: Callable[[str], None] | None = None) -> DownloadPlan:
        """Fetch metadata and chapter index once, without prompting for input."""
        if status:
            status('Fetching title metadata...')
        title = self.titles.get_title(reference)
        if status:
            status('Fetching chapter index...')
        chapters = tuple(self.chapters.get_chapters(title.slug_url))
        if not chapters:
            raise ValueError('No chapters found')
        return DownloadPlan(title, chapters, make_translations(chapters))

    def download(self, reference: str | DownloadPlan, output: str | Path, *,
                 branch_id: int | None = None, limit: int | None = None,
                 progress: Callable[[int, int, str], None] | None = None,
                 resume: bool = False, cache_dir: str | Path = 'output/.cache',
                 delay: float = 1.0, retries: int = 5,
                 status: Callable[[str], None] | None = None,
                 image_mode: str = 'original', image_quality: int = 85,
                 image_max_width: int = 1600,
                 statistics: Callable[[DownloadStatistics], None] | None = None) -> Path:
        if image_mode not in ('original', 'optimized') or not 1 <= image_quality <= 100 or image_max_width < 1:
            raise ValueError('Invalid image optimization settings')
        if delay < 0 or retries < 1:
            raise ValueError('delay must be non-negative and retries must be positive')
        if limit is not None and limit < 1:
            raise ValueError('limit must be positive')
        plan = reference if isinstance(reference, DownloadPlan) else self.prepare(reference, status=status)
        title = plan.title
        chapter_list = plan.chapters
        available = {translation.branch_id for translation in plan.translations}
        if branch_id is None:
            if len(available) > 1:
                raise ValueError('Multiple translations available. Specify branch_id: '
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
        image_count = 0
        original_image_bytes = 0
        embedded_image_bytes = 0
        cached_chapters = 0

        def record_image(original_size: int, embedded_size: int) -> None:
            nonlocal image_count, original_image_bytes, embedded_image_bytes
            image_count += 1
            original_image_bytes += original_size
            embedded_image_bytes += embedded_size
        checkpoints = ChapterCheckpoint(cache_dir, title.id, branch_id)
        fetcher = ChapterFetcher(self.contents, checkpoints)
        processor = ContentProcessor()
        image_cache = Path(cache_dir) / str(title.id) / f"branch-{branch_id if branch_id is not None else 'default'}"
        for index, item in enumerate(selected, 1):
            if status:
                status(f'[{index}/{len(selected)}] Loading chapter {item.volume}/{item.number}...')
            data, from_cache = fetcher.fetch(
                title.slug_url, item, branch_id=branch_id, resume=resume, retries=retries,
            )
            if from_cache:
                cached_chapters += 1
            elif delay > 0 and index < len(selected):
                time.sleep(delay)
            chapter = processor.process(
                data, item, image_cache, status=status,
                image_mode=image_mode, image_quality=image_quality,
                image_max_width=image_max_width, image_stats=record_image,
            )
            rendered.append(chapter)
            if progress is not None:
                progress(index, len(selected), chapter.title)

        if status:
            status('Building EPUB...')
        cover = None
        cover_type = None
        cover_url = getattr(title, 'cover_url', None)
        if cover_url:
            try:
                cover, cover_type = download_cover(cover_url)
            except (httpx.HTTPError, ValueError) as exc:
                if status:
                    status(f'Cover skipped: {exc}')

        result = self.exporter.export(
            output, title=title.title, authors=title.authors, chapters=rendered,
            description=title.description, identifier=f'ranobelib:{title.id}',
            cover=cover, cover_media_type=cover_type,
        )
        if statistics is not None:
            output_path = Path(result)
            statistics(DownloadStatistics(
                chapters=len(rendered), images=image_count,
                original_image_bytes=original_image_bytes,
                embedded_image_bytes=embedded_image_bytes,
                epub_bytes=output_path.stat().st_size if output_path.is_file() else 0,
                cached_chapters=cached_chapters,
            ))
        return result
