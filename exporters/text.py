"""Text and standalone HTML exporters for normalized chapters (stdlib only)."""
from __future__ import annotations

from base64 import b64encode
from html import escape
from pathlib import Path
from xml.etree import ElementTree as ET

XHTML = "{http://www.w3.org/1999/xhtml}"


def _validate(title, chapters):
    if not title or not title.strip() or not chapters:
        raise ValueError("A title and at least one chapter are required")


def _text(chapter):
    root = ET.fromstring(chapter.xhtml)
    if root.tag != XHTML + "html":
        raise ValueError("Expected XHTML chapter")
    body = root.find(XHTML + "body")
    if body is None:
        raise ValueError("Chapter has no body")
    lines = []
    def walk(node):
        if node.tag == XHTML + "img":
            lines.append("[Изображение: " + node.attrib.get("src", "") + "]")
        elif node.tag in {XHTML + "p", XHTML + "h1", XHTML + "h2", XHTML + "h3", XHTML + "li", XHTML + "blockquote"}:
            text = "".join(node.itertext()).strip()
            if text:
                lines.append(text)
            return
        else:
            if node.text and node.text.strip():
                lines.append(node.text.strip())
            for child in node:
                walk(child)
    for child in body:
        walk(child)
    return "\n\n".join(lines)


class TxtExporter:
    def export(self, destination, *, title, authors=(), chapters, description="",
               identifier=None, cover=None, cover_media_type=None, **kwargs):
        _validate(title, chapters)
        pieces = [title, ", ".join(authors)]
        if description:
            pieces.append(description)
        pieces.extend(_text(chapter) for chapter in chapters)
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n\n".join(part for part in pieces if part) + "\n", encoding="utf-8")
        return target


class HtmlExporter:
    def export(self, destination, *, title, authors=(), chapters, description="",
               identifier=None, cover=None, cover_media_type=None, **kwargs):
        _validate(title, chapters)
        sections = []
        for chapter in chapters:
            root = ET.fromstring(chapter.xhtml)
            if root.tag != XHTML + "html":
                raise ValueError("Expected XHTML chapter")
            body = root.find(XHTML + "body")
            if body is None:
                raise ValueError("Chapter has no body")
            images = {href: (payload, media_type) for href, payload, media_type in chapter.images}
            for element in body.iter(XHTML + "img"):
                src = element.attrib.get("src")
                if src not in images:
                    raise ValueError(f"Missing HTML image resource: {src}")
                payload, mime = images[src]
                if mime not in {"image/png", "image/jpeg", "image/gif", "image/webp"}:
                    raise ValueError("Invalid HTML image type")
                element.set("src", f"data:{mime};base64,{b64encode(payload).decode('ascii')}")
            sections.append('<section class="chapter">' + "".join(
                ET.tostring(child, encoding="unicode", method="html") for child in body
            ) + "</section>")
        document = ('<!doctype html><html lang="ru"><head><meta charset="utf-8">'
                    '<meta name="viewport" content="width=device-width,initial-scale=1">'
                    '<title>' + escape(title) + '</title></head><body><main>'
                    '<h1>' + escape(title) + '</h1>' + "".join(sections) + '</main></body></html>')
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(document, encoding="utf-8")
        return target
