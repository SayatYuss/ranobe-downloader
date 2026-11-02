"""MangaLib chapter index source."""
from core.chapter import Chapter
from providers.mangalib.references import parse_title_reference


class ChapterProvider:
    def __init__(self, client):
        self.client = client

    def get_chapters(self, reference: str) -> list[Chapter]:
        slug = parse_title_reference(reference)
        data = self.client.get(f"/manga/{slug}/chapters")["data"]
        if not isinstance(data, list):
            raise ValueError("Expected a chapter list in MangaLib API response")
        return [Chapter.from_api(item) for item in data]
