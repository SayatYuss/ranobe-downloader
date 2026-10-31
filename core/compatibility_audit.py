"""Read-only compatibility sampling for RanobeLib titles."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
import time
import httpx

from core.chapter_xhtml import chapter_to_xhtml
from core.download.images import image_refs, FORMATS
from core.download.plan import make_translations
from urllib.parse import urlsplit
from providers.libsocial.titles import TitleProvider
from providers.libsocial.chapters import ChapterProvider
from providers.libsocial.chapter_content import ChapterContentProvider
from core.download.retry import with_retries


def _order(chapter):
    def key(value):
        try:
            return (0, Decimal(str(value)))
        except (InvalidOperation, ValueError):
            return (1, str(value))
    return key(chapter.volume), key(chapter.number), chapter.index or 0


def _sample_evenly(items: list, count: int) -> list:
    if count >= len(items):
        return items[:]
    if count == 1:
        return [items[0]]
    return [items[i * (len(items) - 1) // (count - 1)] for i in range(count)]


def _inspect(node: Any, types: Counter, marks: Counter) -> None:
    if not isinstance(node, dict):
        types["<invalid>"] += 1
        return
    types[str(node.get("type", "<missing>"))] += 1
    for mark in node.get("marks") or []:
        if isinstance(mark, dict):
            marks[str(mark.get("type", "<missing>"))] += 1
        else:
            marks["<invalid>"] += 1
    children = node.get("content") or []
    if not isinstance(children, list):
        types["<invalid-content>"] += 1
    else:
        for child in children:
            _inspect(child, types, marks)


def audit_title(client, reference: str, *, sample: int = 10,
                branch_id: int | None = None, metadata_only: bool = False,
                retries: int = 3, mode: str | None = None,
                delay: float = 1.0) -> dict[str, Any]:
    if mode is not None and mode not in ('metadata', 'sample', 'full'):
        raise ValueError('Invalid audit mode')
    if mode == 'metadata':
        metadata_only = True
    if delay < 0:
        raise ValueError("delay must be non-negative")
    if sample < 1 or retries < 1:
        raise ValueError("sample and retries must be positive")
    title = with_retries(lambda: TitleProvider(client).get_title(reference), attempts=retries)
    chapters = with_retries(lambda: ChapterProvider(client).get_chapters(title.slug_url), attempts=retries)
    available = [t.branch_id for t in make_translations(tuple(chapters))]
    if branch_id is not None and available and branch_id not in available:
        raise ValueError(f"Branch {branch_id} not found; available: {available}")
    if branch_id is None and len(available) == 1:
        branch_id = available[0]
    selected = [c for c in chapters if branch_id is None or any(b.branch_id == branch_id for b in c.branches)]
    selected.sort(key=_order)
    duplicates = Counter((c.volume, c.number) for c in selected)
    result: dict[str, Any] = {
        "title_id": title.id, "title": title.title, "slug_url": title.slug_url,
        "metadata": {
            "authors": list(title.authors),
            "description_present": bool(title.description),
            "cover_url_present": bool(title.cover_url),
        },
        "chapters_total": len(chapters), "chapters_selected": len(selected),
        "available_branches": available, "selected_branch": branch_id,
        "duplicate_coordinates": [{"volume": v, "number": n, "count": count}
                                  for (v, n), count in duplicates.items() if count > 1],
        "sampled": 0, "passed": 0, "failed": 0, "unverified": 0,
        "node_types": {}, "mark_types": {}, "issues": [],
        "status": "NOT_TESTED" if metadata_only else "COMPATIBLE",
    }
    if len(available) > 1 and branch_id is None:
        result["issues"].append("Multiple branches available: use --branch for a specific translation")
        result["status"] = "INCONCLUSIVE"
    if result["duplicate_coordinates"]:
        result["issues"].append("Duplicate volume/chapter numbers in selected index")
        result["status"] = "INCONCLUSIVE"
    if not selected:
        result["status"] = "INCOMPATIBLE"
        result["issues"].append("No chapters in selected branch")
        return result
    if metadata_only:
        return result
    types: Counter = Counter()
    marks: Counter = Counter()
    inspected = selected if mode == 'full' else _sample_evenly(selected, sample)
    for index, chapter in enumerate(inspected):
        if index and delay:
            time.sleep(delay)
        result["sampled"] += 1
        coordinate = f"{chapter.volume}/{chapter.number}"
        try:
            content = with_retries(lambda: ChapterContentProvider(client).get_chapter(
                title.slug_url, volume=chapter.volume, number=chapter.number,
                branch_id=branch_id), attempts=retries)
            if not isinstance(content.content, (dict, str)):
                raise ValueError(f"Unsupported content format: {type(content.content).__name__}")
            images = {}
            if isinstance(content.content, dict):
                _inspect(content.content, types, marks)
                attachments = {a.get("name"): a for a in getattr(content, "data", {}).get("attachments", [])
                               if isinstance(a, dict)}
                for uid in image_refs(content.content):
                    attached = attachments.get(uid)
                    if attached is None:
                        raise ValueError(f"Missing attachment for image: {uid}")
                    if str(attached.get("extension", "")).lower().lstrip(".") not in FORMATS:
                        raise ValueError(f"Unsupported attachment type: {uid}")
                    path = str(attached.get("originalUrl") or attached.get("url") or "")
                    parsed = urlsplit(path)
                    if (parsed.scheme or parsed.netloc or not path.startswith("/uploads/ranobe/")
                            or ".." in parsed.path.split("/") or parsed.query or parsed.fragment
                            or parsed.path != path):
                        raise ValueError(f"Invalid attachment path: {uid}")
                    if any(ch not in "0123456789abcdef-" for ch in uid.lower()):
                        raise ValueError(f"Invalid image identifier: {uid}")
                    images[uid] = f"images/{uid}.{str(attached.get('extension')).lower().lstrip('.')}"
            chapter_to_xhtml(content.title or chapter.name or coordinate,
                             content.content, images=images)
            result["passed"] += 1
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError) as exc:
            result['unverified'] += 1
            result['issues'].append(f'Chapter {coordinate}: unavailable ({type(exc).__name__}: {exc})')
        except Exception as exc:
            # Preserve partial audit results; do not expose full server payloads.
            result["failed"] += 1
            result["issues"].append(f"Chapter {coordinate}: {type(exc).__name__}: {exc}")
    result["node_types"] = dict(sorted(types.items()))
    result["mark_types"] = dict(sorted(marks.items()))
    if result["failed"]:
        result["status"] = "INCOMPATIBLE"
    elif result["unverified"] or (len(available) > 1 and branch_id is None) or result["duplicate_coordinates"]:
        result["status"] = "INCONCLUSIVE"
    return result
