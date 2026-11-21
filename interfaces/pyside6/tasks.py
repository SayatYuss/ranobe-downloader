"""Background operations executed by the desktop thread runner."""
from __future__ import annotations

import logging
from threading import Event

import httpx
from packaging.version import Version
from PySide6.QtCore import QObject, Signal

from providers.libsocial.client import LibSocialClient
from providers.libsocial.cover import download_cover
from ranobe_downloader import Downloader

log = logging.getLogger(__name__)
RELEASES_API = "https://api.github.com/repos/SayatYuss/ranobe-downloader/releases/latest"


class Task(QObject):
    """Qt bridge that executes one blocking operation in a worker thread."""

    done = Signal(object)
    progress = Signal(int, int, str)
    failed = Signal(str)

    def __init__(self, operation, *args):
        super().__init__()
        self.operation, self.args = operation, args
        self.cancel = Event()

    def run(self):
        try:
            self.done.emit(self.operation(self, *self.args))
        except Exception as exc:
            log.exception("Desktop task failed")
            self.failed.emit(str(exc))


def lookup_book(task, reference, token):
    """Load book metadata and its optional cover."""
    with Downloader(token=token) as downloader:
        book = downloader.get_book(reference)
    cover = None
    try:
        url = getattr(book._plan.title, "cover_url", None)
        if url:
            cover, _ = download_cover(url)
    except Exception:
        log.info("Cover unavailable", exc_info=True)
    return book, cover


def verify_token(task, token):
    with LibSocialClient(token) as client:
        user = client.get_current_user()
    return user["username"]


def check_latest_release(task, current_version):
    response = httpx.get(
        RELEASES_API,
        headers={"Accept": "application/vnd.github+json"},
        timeout=5,
    )
    response.raise_for_status()
    release = response.json()
    latest = Version(release["tag_name"].removeprefix("v"))
    if latest <= Version(current_version):
        return None
    return {
        "version": str(latest),
        "url": release["html_url"],
        "notes": release.get("body", ""),
    }


class DownloadCancelled(Exception):
    def __str__(self):
        return "CANCELLED: download interrupted"


def perform_download(task, book, branch, fmt, start_id, end_id, path, cache, token):
    """Download one queued book while observing cooperative cancellation."""

    def check_cancel(*_):
        if task.cancel.is_set():
            raise DownloadCancelled()

    def progress(current, total, chapter):
        check_cancel()
        task.progress.emit(current, total, chapter)

    check_cancel()
    with Downloader(token=token) as downloader:
        return downloader.download(
            book,
            branch_id=branch,
            format=fmt,
            output=path,
            chapter_start_id=start_id,
            chapter_end_id=end_id,
            cache_dir=cache,
            resume=True,
            progress=progress,
            status=check_cancel,
        )
