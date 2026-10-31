import httpx


class LibSocialClient:
    BASE_URL = "https://api.imglib.info/api"

    def __init__(self, token: str | None = None):
        headers = {
            "Site-Id": "3",
            "Accept": "application/json",
        }

        if token:
            headers["Authorization"] = f"Bearer {token}"

        self._client = httpx.Client(
            base_url=self.BASE_URL,
            headers=headers,
            timeout=30,
        )

    def get_current_user(self) -> dict:
        response = self._client.get("/auth/me")
        response.raise_for_status()
        return response.json()["data"]

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        
    def get(self, path: str, params=None) -> dict:
        response = self._client.get(path, params=params)
        response.raise_for_status()
        return response.json()