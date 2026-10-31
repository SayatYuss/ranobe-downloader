"""Convert structured RanobeLib chapter nodes to EPUB XHTML."""
from html import escape
from xml.etree import ElementTree


def _render(node: dict) -> str:
    kind = node.get('type')
    if kind == 'text':
        result = escape(str(node.get('text') or ''))
        for mark in node.get('marks') or []:
            tag = {'bold': 'strong', 'italic': 'em', 'underline': 'u', 'strike': 's'}.get(mark.get('type'))
            if tag:
                result = f'<{tag}>{result}</{tag}>'
        return result
    if kind == 'hardBreak':
        return '<br />'
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
    inner = ''.join(_render(item) for item in children)
    return inner if tag is None else f'<{tag}>{inner}</{tag}>'


def chapter_to_xhtml(title: str, document: dict, language: str = 'ru') -> str:
    """Convert rich-text chapter to self-contained text-only XHTML.

    Unknown media types are rejected, not silently discarded.
    """
    if not isinstance(document, dict):
        raise ValueError('Structured document required; HTML conversion not yet supported')
    if not language or not language.replace('-', '').isalpha():
        raise ValueError('Invalid language')
    name = escape(title)
    body = _render(document)
    result = ('<?xml version="1.0" encoding="utf-8"?>\n'
              f'<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{language}">'
              f'<head><title>{name}</title></head><body><h1>{name}</h1>{body}</body></html>')
    ElementTree.fromstring(result)
    return result
