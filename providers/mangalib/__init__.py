"""MangaLib provider implementation."""
from providers.mangalib.adapter import MangaLibAdapter
from providers.mangalib.client import MangaLibClient
from providers.mangalib.references import is_mangalib_reference, parse_title_reference

__all__ = ["MangaLibAdapter", "MangaLibClient", "is_mangalib_reference", "parse_title_reference"]
