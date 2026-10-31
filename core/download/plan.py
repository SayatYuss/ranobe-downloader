"""Prepared book metadata, independent of any user interface."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Translation:
    branch_id: int
    chapter_count: int
    name: str | None = None


@dataclass(frozen=True)
class DownloadPlan:
    title: Any
    chapters: tuple[Any, ...]
    translations: tuple[Translation, ...]


def make_translations(chapters: tuple[Any, ...]) -> tuple[Translation, ...]:
    counts: dict[int, int] = {}
    names: dict[int, str] = {}
    for chapter in chapters:
        seen: set[int] = set()
        for branch in chapter.branches:
            branch_id = branch.branch_id
            if branch_id is None or branch_id in seen:
                continue
            seen.add(branch_id)
            counts[branch_id] = counts.get(branch_id, 0) + 1
            if branch_id not in names:
                teams = getattr(branch, "teams", ()) or ()
                name = ", ".join(t.name for t in teams if getattr(t, "name", None))
                name = name or getattr(branch, "username", None)
                if name:
                    names[branch_id] = name
    return tuple(
        Translation(branch_id, count, names.get(branch_id))
        for branch_id, count in sorted(counts.items())
    )
