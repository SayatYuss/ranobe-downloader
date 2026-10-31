"""Summary of a completed EPUB download."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DownloadStatistics:
    chapters: int
    images: int
    original_image_bytes: int
    embedded_image_bytes: int
    epub_bytes: int
    cached_chapters: int = 0

    @property
    def saved_image_bytes(self) -> int:
        return max(0, self.original_image_bytes - self.embedded_image_bytes)

    @property
    def saved_image_percent(self) -> float:
        if not self.original_image_bytes:
            return 0.0
        return self.saved_image_bytes / self.original_image_bytes * 100
