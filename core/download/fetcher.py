"""Chapter retrieval and checkpoint validation, independent of EPUB rendering."""
from __future__ import annotations

from core.chapter_content import ChapterContent, ChapterContentUnavailable
from core.download.checkpoint import ChapterCheckpoint
from core.download.retry import with_retries


class ChapterFetcher:
    def __init__(self, source, checkpoints: ChapterCheckpoint):
        self.source = source
        self.checkpoints = checkpoints

    def fetch(self, reference: str, item, *, branch_id: int | None = None,
              resume: bool = False, retries: int = 5) -> tuple[dict, bool]:
        data = (self.checkpoints.load(item.id, volume=item.volume, number=item.number)
                if resume else None)
        if data is not None:
            return data, True
        raw = with_retries(
            lambda: self.source.get_chapter(
                reference, volume=item.volume, number=item.number, branch_id=branch_id),
            attempts=retries,
        )
        data = raw.data
        reason = ChapterContent.from_api(data).unavailable_reason
        if reason:
            raise ChapterContentUnavailable(f"Chapter {item.volume}/{item.number}: {reason}")
        if not isinstance(data.get("content"), (dict, str)):
            raise ValueError(f"Chapter {item.volume}/{item.number}: unsupported content")
        self.checkpoints.save(item.id, data, volume=item.volume, number=item.number)
        return data, False
