"""Minimal EPUB 3 exporter (stdlib only): metadata, navigation, and XHTML chapters."""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED


@dataclass(frozen=True)
class EpubChapter:
    title: str
    xhtml: str


class EpubExporter:
    def export(
        self,
        destination: str | Path,
        *,
        title: str,
        authors: tuple[str, ...] = (),
        chapters: list[EpubChapter],
        language: str = "ru",
        identifier: str | None = None,
        description: str = "",
    ) -> Path:
        if not title.strip() or not chapters:
            raise ValueError("A title and at least one chapter are required")
        if not language or not language.replace("-", "").isalpha():
            raise ValueError("Invalid language")
        for chapter in chapters:
            root = ElementTree.fromstring(chapter.xhtml)
            if root.tag != "{http://www.w3.org/1999/xhtml}html":
                raise ValueError("Each chapter must be a valid XHTML document")

        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        book_id = identifier or f"urn:uuid:{uuid4()}"
        e = lambda s: escape(str(s), quote=True)

        items = []
        spine = []
        navigation = []
        for index, chapter in enumerate(chapters, 1):
            filename = f"chapter-{index:04}.xhtml"
            items.append(f'<item id="c{index}" href="{filename}" media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="c{index}"/>')
            navigation.append(f'<li><a href="{filename}">{e(chapter.title)}</a></li>')

        creators = "".join(f"<dc:creator>{e(author)}</dc:creator>" for author in authors)
        synopsis = f"<dc:description>{e(description)}</dc:description>" if description else ""
        opf = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
            f'<dc:identifier id="uid">{e(book_id)}</dc:identifier>'
            f'<dc:title>{e(title)}</dc:title><dc:language>{e(language)}</dc:language>'
            f'{creators}{synopsis}</metadata><manifest>'
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
            f'{"".join(items)}</manifest><spine>{"".join(spine)}</spine></package>'
        )
        nav = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
            f'<head><title>{e(title)}</title></head><body>'
            f'<nav epub:type="toc" id="toc"><h1>Содержание</h1><ol>{"".join(navigation)}</ol></nav>'
            '</body></html>'
        )
        container = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="OEBPS/package.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>'
        )
        with ZipFile(destination, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip", compress_type=ZIP_STORED)
            archive.writestr("META-INF/container.xml", container, compress_type=ZIP_DEFLATED)
            archive.writestr("OEBPS/package.opf", opf, compress_type=ZIP_DEFLATED)
            archive.writestr("OEBPS/nav.xhtml", nav, compress_type=ZIP_DEFLATED)
            for index, chapter in enumerate(chapters, 1):
                archive.writestr(
                    f"OEBPS/chapter-{index:04}.xhtml",
                    chapter.xhtml.encode("utf-8"),
                    compress_type=ZIP_DEFLATED,
                )
        return destination
