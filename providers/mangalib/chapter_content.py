"""MangaLib page-list adapter for the shared chapter image pipeline."""
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from core.chapter_content import ChapterContent
from providers.mangalib.references import parse_title_reference

PAGES_BASE_URL = "https://img3.cdnlibs.org"


def _page_attachment(page: dict) -> dict:
    path = str(page.get("url") or "")
    if path.startswith("//"):
        path = PAGES_BASE_URL + path[1:]
    elif path.startswith("/"):
        path = PAGES_BASE_URL + path
    parsed = urlsplit(path)
    if (parsed.scheme != "https" or parsed.hostname != "img3.cdnlibs.org"
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or parsed.query or parsed.fragment):
        raise ValueError("Untrusted MangaLib page URL")
    suffix = PurePosixPath(parsed.path).suffix.lower().lstrip(".")
    if suffix not in {"jpg", "jpeg", "png", "gif", "webp"}:
        raise ValueError(f"Unsupported MangaLib page format: {suffix or 'unknown'}")
    page_id = page.get("id")
    if page_id is None:
        raise ValueError("MangaLib page is missing its ID")
    uid = str(page_id)
    if not uid.isdecimal():
        raise ValueError("Invalid MangaLib page ID")
    return {"name": uid, "extension": suffix, "originalUrl": path}


class ChapterContentProvider:
    def __init__(self, client):
        self.client = client

    def get_chapter(self, reference: str, *, volume: str, number: str,
                    branch_id: int | None = None) -> ChapterContent:
        if not str(volume).strip() or not str(number).strip():
            raise ValueError("Volume and chapter number are required")
        params = {"volume": str(volume), "number": str(number)}
        if branch_id is not None:
            if type(branch_id) is not int or branch_id < 0:
                raise ValueError("branch_id must be a non-negative integer")
            params["branch_id"] = branch_id
        slug = parse_title_reference(reference)
        data = self.client.get(f"/manga/{slug}/chapter", params=params)["data"]
        pages = data.get("pages")
        if not isinstance(pages, list) or not pages:
            raise ValueError("MangaLib chapter has no pages")
        pages = sorted(pages, key=lambda item: int(item.get("slug") or 0))
        attachments = [_page_attachment(page) for page in pages]
        data = dict(data)
        data["attachments"] = attachments
        data["image_pages"] = True
        data["content"] = {"type": "doc", "content": [
            {"type": "image", "attrs": {"images": [{"image": item["name"]}]}}
            for item in attachments
        ]}
        return ChapterContent.from_api(data)
