"""Download and assemble a RanobeLib title in a single command."""
import argparse
from pathlib import Path

import httpx

from core.auth.storage import KeyringTokenStorage
from core.book_downloader import BookDownloader
from providers.libsocial.client import LibSocialClient


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('reference', help='Title ID, ID--slug, or RanobeLib URL')
    parser.add_argument('--branch', type=int, help='Translation branch ID')
    parser.add_argument('--limit', type=int, help='Download only first N chapters (for testing)')
    parser.add_argument('--output', type=Path, help='Output EPUB path (default: output/<id>.epub)')
    parser.add_argument('--resume', action='store_true', help='Reuse verified cached chapters')
    parser.add_argument('--cache-dir', type=Path, default=Path('output/.cache'))
    parser.add_argument('--delay', type=float, default=1.0, help='Seconds between downloads')
    parser.add_argument('--retries', type=int, default=5, help='Maximum attempts per chapter')


def execute(args: argparse.Namespace) -> None:
    try:
        with LibSocialClient(KeyringTokenStorage().load()) as client:
            def report(current, total, chapter):
                print(f'[{current}/{total}] {chapter}')
            # Filename is derived from the API's stable numeric ID, not user input.
            downloader = BookDownloader(client)
            title = downloader.titles.get_title(args.reference)
            target = args.output or Path('output') / f'{title.id}.epub'
            # Keep a single fetched title available for the workflow.
            downloader.titles.get_title = lambda reference: title
            result = downloader.download(args.reference, target,
                                         branch_id=args.branch, limit=args.limit,
                                         progress=report, resume=args.resume,
                                         cache_dir=args.cache_dir, delay=args.delay,
                                         retries=args.retries)
        print(f'Saved: {result}')
    except (httpx.HTTPError, ValueError, KeyError, TypeError, OSError) as exc:
        raise SystemExit(f'Download failed: {exc}') from exc


def main() -> None:
    parser = argparse.ArgumentParser(description='Download a RanobeLib title as EPUB')
    configure_parser(parser)
    execute(parser.parse_args())


if __name__ == '__main__':
    main()
