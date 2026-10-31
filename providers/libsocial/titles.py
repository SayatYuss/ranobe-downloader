from core.title import TITLE_FIELDS, TitleMetadata, parse_title_reference
from providers.libsocial.client import LibSocialClient


class TitleProvider:
    def __init__(self, client: LibSocialClient) -> None:
        self.client = client

    def get_title(self, reference: str) -> TitleMetadata:
        slug_url = parse_title_reference(reference)
        params = [(f"fields[{index}]", field) for index, field in enumerate(TITLE_FIELDS)]
        payload = self.client.get(f"/manga/{slug_url}", params=params)
        return TitleMetadata.from_api(payload["data"])
