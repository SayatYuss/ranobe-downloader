"""MangaLib title metadata source."""
from core.title import TITLE_FIELDS, TitleMetadata
from providers.mangalib.references import parse_title_reference


class TitleProvider:
    def __init__(self, client):
        self.client = client

    def get_title(self, reference: str) -> TitleMetadata:
        slug = parse_title_reference(reference)
        fields = list(TITLE_FIELDS) + [
            "background", "releaseDate", "country", "type_id", "caution",
            "views", "close_view", "rate_avg", "rate", "status_id",
            "manga_status_id", "chap_count", "artists", "format",
        ]
        params = [(f"fields[{index}]", field) for index, field in enumerate(dict.fromkeys(fields))]
        payload = self.client.get(f"/manga/{slug}", params=params)["data"]
        return TitleMetadata.from_api(payload)
