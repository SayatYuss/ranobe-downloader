from core.chapter_content import ChapterContent
from core.title import parse_title_reference
from providers.libsocial.client import LibSocialClient


class ChapterContentProvider:
    """Retrieve a single chapter; branch_id selects the translation if provided."""

    def __init__(self, client: LibSocialClient) -> None:
        self.client = client

    def get_chapter(
        self,
        reference: str,
        *,
        volume: str,
        number: str,
        branch_id: int | None = None,
    ) -> ChapterContent:
        if not str(volume).strip() or not str(number).strip():
            raise ValueError("Volume and chapter number are required")

        params: dict[str, str | int] = {
            "volume": str(volume),
            "number": str(number),
        }
        if branch_id is not None:
            if branch_id < 0:
                raise ValueError("branch_id cannot be negative")
            params["branch_id"] = branch_id

        slug_url = parse_title_reference(reference)
        response = self.client.get(f"/manga/{slug_url}/chapter", params=params)
        return ChapterContent.from_api(response["data"])
