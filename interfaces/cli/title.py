"""Standalone metadata CLI: python -m interfaces.cli.title <ID--slug or URL>."""

import argparse
import json
from dataclasses import asdict

import httpx

from core.auth.storage import KeyringTokenStorage
from providers.libsocial.client import LibSocialClient
from providers.libsocial.titles import TitleProvider


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch RanobeLib title metadata")
    parser.add_argument("reference", help="Title ID, ID--slug, or RanobeLib URL")
    parser.add_argument("--json", action="store_true", help="Print normalized metadata as JSON")
    args = parser.parse_args()

    token = KeyringTokenStorage().load()
    try:
        with LibSocialClient(token) as client:
            title = TitleProvider(client).get_title(args.reference)
    except (ValueError, KeyError, httpx.HTTPError) as exc:
        parser.exit(1, f"Metadata request failed: {exc}\n")

    if args.json:
        print(json.dumps(asdict(title), ensure_ascii=False, indent=2))
    else:
        print(f"{title.title} (ID: {title.id})")
        print(f"Author(s): {', '.join(title.authors) or 'unknown'}")
        print(f"Uploaded items: {title.uploaded_count if title.uploaded_count is not None else 'unknown'}")
        print(f"Translation branches: {title.branches_count if title.branches_count is not None else 'unknown'}")


if __name__ == "__main__":
    main()
