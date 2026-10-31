"""Atomic on-disk chapter checkpoint storage, keyed by title and translation."""
from __future__ import annotations

import json
from hashlib import sha256
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


class ChapterCheckpoint:
    def __init__(self, root: str | Path, title_id: int, branch_id: int | None):
        branch = str(branch_id) if branch_id is not None else "default"
        self.directory = Path(root) / str(title_id) / f"branch-{branch}" / "chapters"

    def path(self, chapter_id: int) -> Path:
        return self.directory / f"{chapter_id}.json"

    def load(self, chapter_id: int, *, volume: str, number: str) -> dict | None:
        path = self.path(chapter_id)
        if not path.exists():
            return None
        try:
            raw = path.read_bytes()
            digest_file = path.with_suffix(".sha256")
            if digest_file.is_file():
                if digest_file.read_text(encoding="ascii").strip() != sha256(raw).hexdigest():
                    return None
            data = json.loads(raw.decode("utf-8"))
        except (OSError, ValueError, UnicodeError):
            return None
        if not self._valid(data, volume=volume, number=number):
            return None
        return data

    @staticmethod
    def _valid(data: object, *, volume: str, number: str) -> bool:
        return (
            isinstance(data, dict)
            and isinstance(data.get("content"), (dict, str))
            and str(data.get("volume")) == str(volume)
            and str(data.get("number")) == str(number)
        )

    def save(self, chapter_id: int, data: dict, *, volume: str, number: str) -> None:
        if not self._valid(data, volume=volume, number=number):
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
            # Optional checksum: old checkpoints without a sidecar remain readable.
            digest = sha256(self.path(chapter_id).read_bytes()).hexdigest()
            sidecar = self.path(chapter_id).with_suffix(".sha256")
            with NamedTemporaryFile(mode="w", encoding="ascii", dir=self.directory,
                                    prefix=".checksum-", suffix=".tmp", delete=False) as handle:
                checksum_temp = Path(handle.name)
                try:
                    handle.write(digest)
                    handle.flush()
                    os.fsync(handle.fileno())
                finally:
                    pass
            try:
                os.replace(checksum_temp, sidecar)
            finally:
                checksum_temp.unlink(missing_ok=True)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
