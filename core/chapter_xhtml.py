"""Convert structured RanobeLib chapter nodes to EPUB XHTML."""
from html import escape
from html.parser import HTMLParser
from xml.etree import ElementTree


def _render(node: dict, images: dict | None = None) -> str:
    kind = node.get('type')
    if kind == 'text':
        result = escape(str(node.get('text') or ''))
        for mark in node.get('marks') or []:
            tag = {'bold': 'strong', 'italic': 'em', 'underline': 'u', 'strike': 's'}.get(mark.get('type'))
            if tag:
                result = f'<{tag}>{result}</{tag}>'
        return result
    if kind == 'image':
        refs = (node.get('attrs') or {}).get('images') or []
        if not refs:
            raise ValueError('Image node has no images')
        parts = []
        for item in refs:
            uid = item.get('image') if isinstance(item, dict) else None
            if not isinstance(uid, str) or not images or uid not in images:
                raise ValueError(f'Image attachment not resolved: {uid}')
            href = images[uid]
            parts.append(f'<img src="{escape(href, quote=True)}" alt="" />')
        return ''.join(parts)
    if kind == 'hardBreak':
        return '<br />'
    if kind == 'horizontalRule':
        return '<hr />'
    tags = {'doc': None, 'paragraph': 'p', 'blockquote': 'blockquote',
            'bulletList': 'ul', 'orderedList': 'ol', 'listItem': 'li'}
    if kind == 'heading':
        level = (node.get('attrs') or {}).get('level', 2)
        tag = f'h{level}' if type(level) is int and 1 <= level <= 6 else 'h2'
    elif kind in tags:
        tag = tags[kind]
    else:
        raise ValueError(f'Unsupported chapter node: {kind}')
    children = node.get('content') or []
    if not isinstance(children, list):
        raise ValueError('Expected content list')
    inner = ''.join(_render(item, images) for item in children)
    return inner if tag is None else f'<{tag}>{inner}</{tag}>'


class _SafeHtml(HTMLParser):
    """Keep text and basic formatting, reject media and active content."""

    TAGS = {'p', 'blockquote', 'strong', 'em', 'b', 'i', 'u',
            's', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
    VOID = {'br', 'hr'}

    def __init__(self, html_images=None):
        super().__init__(convert_charrefs=True)
        self.html_images = html_images or {}
        self.parts = []
        self.stack = []
        self.blocked = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.blocked += 1
            self.stack.append(('blocked', tag))
        elif tag == 'img':
            if self.blocked:
                return
            src = dict(attrs).get('src')
            href = self.html_images.get(src)
            if not href:
                raise ValueError('HTML media requires attachment support: img (unresolved)')
            self.parts.append(f'<img src="{escape(href, quote=True)}" alt="" />')
        elif tag in {'video', 'audio', 'iframe', 'svg', 'picture'}:
            raise ValueError(f'HTML media requires attachment support: {tag}')
        elif tag in self.VOID:
            if not self.blocked:
                self.parts.append(f'<{tag} />')
        elif tag in self.TAGS:
            self.stack.append(('allowed', tag))
            if not self.blocked:
                self.parts.append(f'<{tag}>')
        else:
            self.stack.append(('ignored', tag))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][1] == tag:
                closing = self.stack[i:]
                del self.stack[i:]
                for mode, name in reversed(closing):
                    if mode == 'blocked':
                        self.blocked -= 1
                    elif mode == 'allowed' and not self.blocked:
                        self.parts.append(f'</{name}>')
                break

    def handle_data(self, data):
        if not self.blocked:
            self.parts.append(escape(data))

    def finish(self):
        for mode, name in reversed(self.stack):
            if mode == 'allowed' and not self.blocked:
                self.parts.append(f'</{name}>')
        return ''.join(self.parts)


def chapter_to_xhtml(title: str, document: dict | str, language: str = 'ru', *, images: dict | None = None,
                     html_images: dict[str, str] | None = None) -> str:
    """Convert rich-text chapter to self-contained text-only XHTML.

    Unknown media types are rejected, not silently discarded.
    """
    if not isinstance(document, (dict, str)):
        raise ValueError('Structured document or HTML string required')
    if not language or not language.replace('-', '').isalpha():
        raise ValueError('Invalid language')
    name = escape(title)
    if isinstance(document, str):
        parser = _SafeHtml(html_images=html_images)
        parser.feed(document)
        body = parser.finish()
    else:
        body = _render(document, images)
    result = ('<?xml version="1.0" encoding="utf-8"?>\n'
              f'<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{language}">'
              f'<head><title>{name}</title></head><body><h1>{name}</h1>{body}</body></html>')
    ElementTree.fromstring(result)
    return result
