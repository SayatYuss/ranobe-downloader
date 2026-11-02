"""MangaLib adapter for the shared downloader and EPUB pipeline."""
from core.download.images import load_images
from providers.mangalib.chapter_content import ChapterContentProvider
from providers.mangalib.chapters import ChapterProvider
from providers.mangalib.media import download_cover, fetch_image, _validated_url
from providers.mangalib.titles import TitleProvider


class MangaLibAdapter:
    def __init__(self, client):
        self.titles = TitleProvider(client)
        self.chapters = ChapterProvider(client)
        self.contents = ChapterContentProvider(client)

    def download_cover(self, url):
        return download_cover(url)

    def load_images(self, *args, **kwargs):
        return load_images(
            *args, **kwargs,
            fetch_media=fetch_image,
            validate_attachment=lambda attachment_url: _validated_url(
                {"originalUrl": attachment_url}
            ),
        )

    def resolve_html_images(self, html, attachments):
        # MangaLib chapter content is represented by its page list, not HTML.
        if "<img" in html.lower():
            raise ValueError("Unexpected HTML images in MangaLib page content")
        return {}, []
