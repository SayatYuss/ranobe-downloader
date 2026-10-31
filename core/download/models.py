"""Exporter-neutral representation of a rendered chapter."""
from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedChapter:
    title: str
    xhtml: str
    images: tuple[tuple[str, bytes, str], ...] = ()
