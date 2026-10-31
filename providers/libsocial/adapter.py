"""RanobeLib adapter assembling provider-specific services for the core."""
from providers.libsocial.chapter_content import ChapterContentProvider
from providers.libsocial.chapters import ChapterProvider
from providers.libsocial.titles import TitleProvider
from providers.libsocial.cover import download_cover
from core.download.images import load_images
from providers.libsocial.media import fetch_attachment
from providers.libsocial.media_policy import attachment_path
from core.download.html_images import resolve_html_images


class LibSocialAdapter:
    def __init__(self, client):
        self.titles = TitleProvider(client)
        self.chapters = ChapterProvider(client)
        self.contents = ChapterContentProvider(client)

    def download_cover(self, url):
        return download_cover(url)

    def load_images(self, *args, **kwargs):
        return load_images(*args, **kwargs, fetch_media=fetch_attachment, validate_attachment=attachment_path)

    def resolve_html_images(self, html, attachments):
        return resolve_html_images(html, attachments)
