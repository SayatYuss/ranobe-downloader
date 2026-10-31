from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ChapterContentUnavailable(ValueError):
    """Chapter content was withheld or omitted by the API."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class ChapterContent:
    """Raw chapter payload, retained without lossy HTML/schema conversion.

    RanobeLib may return HTML text, structured document nodes, and media.
    Rendering belongs to a later exporter, not to the API integration.
    """

    data: dict[str, Any]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> ChapterContent:
        if not isinstance(data, dict):
            raise ValueError("Expected a chapter object in the API response")
        return cls(data=data)

    @property
    def content(self) -> Any:
        return self.data.get("content")

    @property
    def restricted_view(self) -> dict[str, Any] | None:
        value = self.data.get("restricted_view")
        return value if isinstance(value, dict) else None

    @property
    def unavailable_reason(self) -> str | None:
        if isinstance(self.content, (dict, str)):
            return None
        restriction = self.restricted_view
        if restriction and restriction.get("is_open") is False and restriction.get("price") is not None:
            return "paid_content"
        if self.content is None:
            return "missing_content"
        return None

    @property
    def pages(self) -> Any:
        return self.data.get("pages")

    @property
    def title(self) -> str | None:
        name = self.data.get("name")
        return name if isinstance(name, str) else None
