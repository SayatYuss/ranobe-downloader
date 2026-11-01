"""Inclusive selection by chapter IDs in the reading-order index."""
from __future__ import annotations


def select_chapter_id_range(chapters: list, start_id: int | None = None,
                            end_id: int | None = None) -> list:
    """Select all entries between two chapter IDs, inclusive, in list order.

    The caller must first filter by translation and sort chapters. IDs identify
    boundaries; they are not compared numerically because API IDs need not
    increase in reading order.
    """
    if start_id is None and end_id is None:
        return chapters
    for name, value in (("chapter_start_id", start_id), ("chapter_end_id", end_id)):
        if value is not None and (type(value) is not int or value < 1):
            raise ValueError(f"{name} must be a positive integer")
    positions = {}
    for i, chapter in enumerate(chapters):
        cid = chapter.id
        if cid in positions:
            raise ValueError(f"Duplicate chapter ID in selected translation: {cid}")
        positions[cid] = i
    for name, value in (("chapter_start_id", start_id), ("chapter_end_id", end_id)):
        if value is not None and value not in positions:
            raise ValueError(f"{name}={value} is not available in selected translation")
    start = positions[start_id] if start_id is not None else 0
    end = positions[end_id] if end_id is not None else len(chapters) - 1
    if start > end:
        raise ValueError("chapter_start_id must precede chapter_end_id")
    return chapters[start:end + 1]
