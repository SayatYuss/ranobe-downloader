from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
    def pages(self) -> Any:
        return self.data.get("pages")

    @property
    def title(self) -> str | None:
        name = self.data.get("name")
        return name if isinstance(name, str) else None
