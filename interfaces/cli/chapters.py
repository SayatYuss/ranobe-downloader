"""Standalone chapters CLI: python -m interfaces.cli.chapters <ID--slug or URL>."""

import argparse
import json
from dataclasses import asdict

import httpx

from core.auth.storage import KeyringTokenStorage
from providers.libsocial.chapters import ChapterProvider
from providers.libsocial.client import LibSocialClient


def main() -> None:
    parser = argparse.ArgumentParser(description="List RanobeLib chapters and translations")
    parser.add_argument("reference", help="Title ID, ID--slug or title URL")
    parser.add_argument("--json", action="store_true", help="Print full normalized list as JSON")
    parser.add_argument("--branch", type=int, help="Keep only chapters with this translation branch")
    args = parser.parse_args()

    try:
        with LibSocialClient(KeyringTokenStorage().load()) as client:
            chapters = ChapterProvider(client).get_chapters(args.reference)
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Chapter request failed: {exc}\n")

    if args.branch is not None:
        chapters = [
            chapter for chapter in chapters
            if any(b.branch_id == args.branch for b in chapter.branches)
        ]

    if args.json:
        print(json.dumps([asdict(chapter) for chapter in chapters], ensure_ascii=False, indent=2))
        return

    print(f"Chapters: {len(chapters)}")
    for chapter in chapters:
        branches = ", ".join(
            f"{branch.branch_id}: {', '.join(t.name for t in branch.teams) or branch.username or 'unknown'}"
            for branch in chapter.branches
        )
        print(
            f"Vol. {chapter.volume}, Ch. {chapter.number} — {chapter.name or 'Untitled'}"
            f" | translations: {branches or 'none'}"
        )


if __name__ == "__main__":
    main()
