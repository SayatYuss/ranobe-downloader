"""Fetch a single RanobeLib chapter and print or save its raw API data."""

import argparse
import json
from pathlib import Path

import httpx

from core.auth.storage import KeyringTokenStorage
from providers.libsocial.chapter_content import ChapterContentProvider
from providers.libsocial.client import LibSocialClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieve RanobeLib chapter content")
    parser.add_argument("reference", help="Title ID, ID--slug, or URL")
    parser.add_argument("--volume", required=True, help="Volume as returned by chapter list")
    parser.add_argument("--number", required=True, help="Chapter number as returned by chapter list")
    parser.add_argument("--branch", type=int, help="Translation branch_id")
    parser.add_argument("--output", type=Path, help="Write chapter JSON to a file")
    args = parser.parse_args()

    try:
        with LibSocialClient(KeyringTokenStorage().load()) as client:
            chapter = ChapterContentProvider(client).get_chapter(
                args.reference,
                volume=args.volume,
                number=args.number,
                branch_id=args.branch,
            )
        serialized = json.dumps(chapter.data, ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(serialized + "\n", encoding="utf-8")
            print(f"Saved: {args.output}")
        else:
            print(serialized)
    except (httpx.HTTPError, ValueError, KeyError, OSError) as exc:
        parser.exit(1, f"Chapter request failed: {exc}\n")


if __name__ == "__main__":
    main()
