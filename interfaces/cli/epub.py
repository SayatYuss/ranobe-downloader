"""Build an EPUB from downloaded chapter JSON files, without API requests."""
import argparse
import json
from pathlib import Path

from core.chapter_xhtml import chapter_to_xhtml
from exporters.epub import EpubChapter, EpubExporter


def main() -> None:
    parser = argparse.ArgumentParser(description="Build EPUB from saved RanobeLib chapter JSON")
    parser.add_argument("chapters", nargs="+", type=Path, help="Chapter JSON files, in reading order")
    parser.add_argument("--output", required=True, type=Path, help="Destination .epub")
    parser.add_argument("--title", required=True, help="Book title")
    parser.add_argument("--author", action="append", default=[], help="Author; repeat for several")
    parser.add_argument("--lang", default="ru", help="EPUB language code")
    args = parser.parse_args()

    chapters = []
    try:
        for path in args.chapters:
            data = json.loads(path.read_text(encoding="utf-8"))
            # API responses saved by chapter_content CLI are already unwrapped.
            content = data["content"]
            chapter_name = data.get("name") or f"Глава {data.get('number', len(chapters) + 1)}"
            chapters.append(
                EpubChapter(
                    chapter_name,
                    chapter_to_xhtml(chapter_name, content, language=args.lang),
                )
            )
        result = EpubExporter().export(
            args.output, title=args.title, authors=tuple(args.author),
            chapters=chapters, language=args.lang,
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(1, f"EPUB build failed: {exc}\n")
    print(f"Saved: {result}")


if __name__ == "__main__":
    main()
