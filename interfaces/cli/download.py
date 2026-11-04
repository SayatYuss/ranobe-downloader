"""Download and assemble a RanobeLib title in a single command."""
import argparse
import re
from pathlib import Path

import httpx

from core.auth.storage import KeyringTokenStorage
from core.book_downloader import BookDownloader, _chapter_order
from core.settings import DownloaderSettings
from exporters.epub import EpubExporter
from exporters.text import TxtExporter, HtmlExporter
from interfaces.cli.translation_selector import select_translation
from providers.libsocial.client import LibSocialClient


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('reference', help='Title ID, ID--slug, or RanobeLib URL')
    parser.add_argument('--branch', type=int, help='Translation branch ID')
    parser.add_argument('--format', choices=('epub', 'txt', 'html'), default=None, help='Output format')
    parser.add_argument('--non-interactive', action='store_true', help='Disable interactive translation menu')
    parser.add_argument('--limit', type=int, help='Download at most N chapters after range selection')
    parser.add_argument('--from', '--chapter-from', dest='chapter_from', metavar='NUMBER',
                        help='First chapter number (inclusive, e.g. 13.4)')
    parser.add_argument('--to', '--chapter-to', dest='chapter_to', metavar='NUMBER',
                        help='Last chapter number (inclusive, e.g. 45)')
    parser.add_argument('--start-id', type=int, help='Inclusive starting chapter ID')
    parser.add_argument('--end-id', type=int, help='Inclusive ending chapter ID')
    parser.add_argument('--list-chapters', action='store_true',
                        help='List chapter numbers for the selected translation without downloading')
    parser.add_argument('--output', type=Path, help='Output path (default: output/<slug_url>_<branch>.<format>)')
    parser.add_argument('--resume', action='store_true', help='Reuse verified cached chapters')
    parser.add_argument('--cache-dir', type=Path, default=None)
    parser.add_argument('--delay', type=float, default=None, help='Seconds between downloads')
    parser.add_argument('--image-mode', choices=('original', 'optimized'), default=None,
                        help='original: embed source files (default); optimized: convert near-opaque PNG to smaller JPEG (requires Pillow)')
    parser.add_argument('--image-quality', type=int, default=None,
                        help='JPEG quality for optimized PNGs, 1-100 (default: 85)')
    parser.add_argument('--image-max-width', type=int, default=None,
                        help='Max width when converting PNGs, in pixels (default: 1600)')
    parser.add_argument('--verbose', action='store_true', help='Show per-image download details')
    parser.add_argument('--retries', type=int, default=None, help='Maximum attempts per chapter')


def _format_size(value: int) -> str:
    return f'{value / (1024 * 1024):.2f} MiB'


def _print_summary(stats) -> None:
    print('\nDownload summary:')
    print(f'  Chapters: {stats.chapters} ({stats.cached_chapters} from cache)')
    print(f'  Images: {stats.images}')
    print(f'  Original images: {_format_size(stats.original_image_bytes)}')
    print(f'  Embedded images: {_format_size(stats.embedded_image_bytes)}')
    print(f'  Image savings: {_format_size(stats.saved_image_bytes)} ({stats.saved_image_percent:.1f}%)')
    print(f'  Output size: {_format_size(stats.epub_bytes)}')
    if stats.skipped_paid_chapters:
        print(f'  Skipped paid chapters: {len(stats.skipped_paid_chapters)}')
        for chapter in stats.skipped_paid_chapters:
            print(f'    - {chapter}')


def execute(args: argparse.Namespace) -> None:
    settings = DownloaderSettings.load()
    settings.validate()
    try:
        print('Connecting to RanobeLib...', flush=True)
        with LibSocialClient(KeyringTokenStorage().load()) as client:
            def report(current, total, chapter):
                print(f'[{current}/{total}] {current / total:.0%}  {chapter}', flush=True)
            # Filename is derived from the API's stable numeric ID, not user input.
            format_name = args.format or settings.format
            exporter = {'epub': EpubExporter, 'txt': TxtExporter, 'html': HtmlExporter}[format_name]()
            downloader = BookDownloader(client, exporter=exporter)
            plan = downloader.prepare(args.reference)
            print(f'Title: {plan.title.title}', flush=True)
            def report_status(message):
                if args.verbose or not (message.startswith('  Downloading image ') or
                                        (message.startswith('[') and 'Loading chapter' in message)):
                    print(message, flush=True)

            branch_id = args.branch if args.branch is not None else settings.branch_id
            if branch_id is None:
                branch_id = select_translation(plan.translations, interactive=not args.non_interactive)
            if args.list_chapters:
                chapters = sorted(
                    (chapter for chapter in plan.chapters
                     if branch_id is None or any(
                         branch.branch_id == branch_id for branch in chapter.branches)),
                    key=_chapter_order,
                )
                if not chapters:
                    raise ValueError('No chapters in selected translation branch')
                for chapter in chapters:
                    cid = getattr(chapter, "id", None)
                    id_label = f" [ID {cid}]" if cid is not None else ""
                    print(f'{chapter.volume}/{chapter.number}{id_label} — {chapter.name or "Без названия"}')
                return
            slug = plan.title.slug_url
            if not re.fullmatch(r"[A-Za-z0-9_-]+", slug):
                raise ValueError("Unsafe title slug for output filename")
            branch_label = str(branch_id) if branch_id is not None else "default"
            target = args.output or Path(settings.output_dir) / f'{slug}_{branch_label}.{format_name}'
            result = downloader.download(plan, target,
                                         branch_id=branch_id, limit=args.limit,
                                         chapter_from=args.chapter_from, chapter_to=args.chapter_to,
                                         chapter_start_id=args.start_id, chapter_end_id=args.end_id,
                                         progress=report, resume=args.resume,
                                         cache_dir=args.cache_dir, delay=args.delay,
                                         retries=args.retries,
                                         image_mode=args.image_mode,
                                         image_quality=args.image_quality,
                                         image_max_width=args.image_max_width,
                                         status=report_status,
                                         statistics=_print_summary)
        print(f'Saved: {result}')
    except (httpx.HTTPError, ValueError, KeyError, TypeError, OSError) as exc:
        raise SystemExit(f'Download failed: {exc}') from exc


def main() -> None:
    parser = argparse.ArgumentParser(description='Download a RanobeLib title as EPUB')
    configure_parser(parser)
    execute(parser.parse_args())


if __name__ == '__main__':
    main()
