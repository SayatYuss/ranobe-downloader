from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


ALLOWED_HOSTS = {"ranobelib.me", "www.ranobelib.me", "api.imglib.info"}
TITLE_FIELDS = (
    "eng_name", "otherNames", "summary", "releaseDate", "genres",
    "tags", "teams", "authors", "publisher", "metadata", "chap_count",
)


def parse_title_reference(reference: str) -> str:
    """Return a RanobeLib slug_url from an ID/slug_url or a site URL."""
    value = reference.strip()
    if not value:
        raise ValueError("Title reference cannot be empty")
    if "://" in value:
        url = urlparse(value)
        if url.scheme != "https" or url.hostname not in ALLOWED_HOSTS:
            raise ValueError("Only HTTPS RanobeLib / imglib title URLs are accepted")
        parts = [part for part in url.path.split("/") if part]
        # Site URLs: /ru/manga/<slug_url> or /ru/book/<slug_url>;
        # API URLs: /api/manga/<slug_url>
        if "manga" in parts:
            index = parts.index("manga")
        elif "book" in parts:
            index = parts.index("book")
        else:
            raise ValueError("Title URL must contain /manga/ or /book/")
        if index + 1 >= len(parts):
            raise ValueError("Missing title in URL")
        value = parts[index + 1]
    if value.isdigit():
        return value
    if "--" not in value or not value.split("--", 1)[0].isdigit():
        raise ValueError("Expected a numeric title ID or ID--slug")
    if any(c in value for c in "/?#"):
        raise ValueError("Invalid title reference")
    return value


def summary_as_text(node: object) -> str:
    """Extract readable text from the structured description (Tiptap/ProseMirror)."""
    if not isinstance(node, dict):
        return ""
    kind = node.get("type")
    if kind == "text":
        return str(node.get("text", ""))
    children = node.get("content", [])
    if not isinstance(children, list):
        return ""
    text = "".join(summary_as_text(child) for child in children)
    if kind in {"paragraph", "heading", "listItem"} and text:
        return text + "\n"
    return text


@dataclass(frozen=True)
class TitleMetadata:
    id: int
    slug_url: str
    title: str
    original_title: str
    authors: tuple[str, ...]
    description: str
    cover_url: str | None
    release_year: str | None
    genres: tuple[str, ...]
    uploaded_count: int | None
    branches_count: int | None

    @classmethod
    def from_api(cls, data: dict) -> TitleMetadata:
        counts = data.get("items_count") or {}
        metadata = data.get("metadata") or {}
        return cls(
            id=data["id"],
            slug_url=data["slug_url"],
            title=data.get("rus_name") or data.get("name") or "",
            original_title=data.get("eng_name") or data.get("name") or "",
            authors=tuple(a["name"] for a in (data.get("authors") or []) if a.get("name")),
            description=summary_as_text(data.get("summary")).strip(),
            cover_url=(data.get("cover") or {}).get("default"),
            release_year=data.get("releaseDate"),
            genres=tuple(g["name"] for g in (data.get("genres") or []) if g.get("name")),
            uploaded_count=counts.get("uploaded"),
            branches_count=(metadata.get("count") or {}).get("branches"),
        )
