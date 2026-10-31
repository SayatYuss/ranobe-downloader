"""Select an inclusive chapter-number range after translation filtering."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation


def chapter_number(value: str | int | Decimal) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("Chapter number must be a decimal string or integer")
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid chapter number: {value!r}") from exc
    if not number.is_finite():
        raise ValueError("Chapter number must be finite")
    return number


def select_chapter_range(chapters: list, chapter_from=None, chapter_to=None) -> list:
    """Inclusive range, using chapter numbers rather than list positions.

    Chapters should already be restricted to one translation branch and sorted
    in reading order. Range bounds must match real chapter numbers; repeated
    boundary numbers in different volumes are ambiguous.
    """
    if chapter_from is None and chapter_to is None:
        return chapters
    lower = chapter_number(chapter_from) if chapter_from is not None else None
    upper = chapter_number(chapter_to) if chapter_to is not None else None
    if lower is not None and upper is not None and lower > upper:
        raise ValueError("chapter_from cannot be greater than chapter_to")
    numbers = []
    for ch in chapters:
        try:
            numbers.append(chapter_number(ch.number))
        except ValueError as exc:
            raise ValueError(f"Non-numeric chapter number in selected branch: {ch.number!r}") from exc
    for label, bound in (("chapter_from", lower), ("chapter_to", upper)):
        if bound is None:
            continue
        matches = [ch for ch, number in zip(chapters, numbers) if number == bound]
        if not matches:
            raise ValueError(f"{label}={bound} is not available in selected translation")
        if len({str(ch.volume) for ch in matches}) > 1:
            raise ValueError(f"{label}={bound} is ambiguous across volumes")
    return [
        chapter for chapter, number in zip(chapters, numbers)
        if (lower is None or number >= lower) and (upper is None or number <= upper)
    ]
