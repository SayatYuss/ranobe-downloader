"""Atomic on-disk chapter checkpoint storage, keyed by title and translation."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


class ChapterCheckpoint:
    def __init__(self, root: str | Path, title_id: int, branch_id: int | None):
        branch = str(branch_id) if branch_id is not None else "default"
        self.directory = Path(root) / str(title_id) / f"branch-{branch}" / "chapters"

    def path(self, chapter_id: int) -> Path:
        return self.directory / f"{chapter_id}.json"

    def load(self, chapter_id: int) -> dict | None:
        path = self.path(chapter_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeError):
            return None
        if not isinstance(data, dict) or data.get("id") != chapter_id or not isinstance(data.get("content"), dict):
            return None
        return data

    def save(self, chapter_id: int, data: dict) -> None:
        if data.get("id") != chapter_id or not isinstance(data.get("content"), dict):
            raise ValueError("Chapter checkpoint does not match requested chapter")
        self.directory.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.directory,
                                    prefix=".chapter-", suffix=".tmp", delete=False) as handle:
                temp_path = Path(handle.name)
                json.dump(data, handle, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path(chapter_id))
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
