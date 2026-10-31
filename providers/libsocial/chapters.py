from core.chapter import Chapter
from core.title import parse_title_reference
from providers.libsocial.client import LibSocialClient


class ChapterProvider:
    """Fetch the chapter index; each chapter may have multiple translation branches."""

    def __init__(self, client: LibSocialClient) -> None:
        self.client = client

    def get_chapters(self, reference: str) -> list[Chapter]:
        slug_url = parse_title_reference(reference)
        payload = self.client.get(f"/manga/{slug_url}/chapters")
        data = payload["data"]
        if not isinstance(data, list):
            raise ValueError("Expected a chapter list in API response")
        # Preserve server order and the original string volume/number values.
        return [Chapter.from_api(item) for item in data]
