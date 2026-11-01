"""Opt-in FastAPI interface. Bind to loopback unless protected by an upstream gateway."""
from __future__ import annotations

import os
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Event, Lock
from typing import Callable
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ranobe_downloader import Downloader

FORMATS = {"epub", "txt", "html"}


class DownloadRequest(BaseModel):
    reference: str = Field(min_length=1, max_length=2048)
    format: str = "epub"
    branch_id: int | None = None
    limit: int | None = Field(default=None, ge=1)
    resume: bool = False
    chapter_from: str | None = Field(default=None, max_length=64)
    chapter_to: str | None = Field(default=None, max_length=64)
    chapter_start_id: int | None = Field(default=None, ge=1)
    chapter_end_id: int | None = Field(default=None, ge=1)


@dataclass
class Job:
    id: str
    format: str
    state: str = "queued"
    current: int = 0
    total: int = 0
    message: str = ""
    filename: str | None = None
    error: str | None = None
    path: Path | None = field(default=None, repr=False)
    cancel: Event = field(default_factory=Event, repr=False)
    updated: float = field(default_factory=time.time)
    queue_position: int | None = None

    def public(self) -> dict:
        data = {k: v for k, v in vars(self).items() if k not in ("path", "cancel")}
        return data


def create_app(*, downloader_factory: Callable[[], Downloader] = Downloader,
               output_dir: str | Path = "output/api",
               max_workers: int = 2, max_jobs: int = 50,
               max_queue: int = 20, retention_seconds: int = 3600) -> FastAPI:
    """Create an in-process job server. Jobs are not persisted across restarts."""
    if max_workers < 1 or max_jobs < 1 or max_queue < 0 or retention_seconds < 1:
        raise ValueError("max_workers and max_jobs must be positive")
    executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ranobe-api")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title="Ranobe Downloader API", version="0.1", lifespan=lifespan)
    base = Path(output_dir).resolve()
    jobs: dict[str, Job] = {}
    lock = Lock()
    futures: dict[str, Future] = {}
    queue: list[str] = []

    def refresh_queue():
        queue[:] = [jid for jid in queue if jid in jobs and jobs[jid].state == "queued"]
        for index, jid in enumerate(queue, 1):
            jobs[jid].queue_position = index

    def cleanup_expired():
        now = time.time()
        paths = []
        with lock:
            for jid, job in list(jobs.items()):
                if job.state in ("completed", "failed", "cancelled") and now - job.updated >= retention_seconds:
                    paths.append(base / f"{jid}.{job.format}")
                    jobs.pop(jid)
                    futures.pop(jid, None)
            refresh_queue()
        for path in paths:
            path.unlink(missing_ok=True)

    def finish(job, state, error=None):
        job.state = state
        job.error = error
        job.updated = time.time()
        job.queue_position = None


    def snapshot(job_id: str) -> dict:
        cleanup_expired()
        with lock:
            job = jobs.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Unknown download")
            return job.public()

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/books")
    def book_info(reference: str = Query(min_length=1, max_length=2048)):
        try:
            with downloader_factory() as downloader:
                book = downloader.get_book(reference)
                return {
                    "id": book.id, "title": book.title, "slug_url": book.slug_url,
                    "authors": list(book.authors), "chapter_count": book.chapter_count,
                    "translations": [
                        {"branch_id": t.branch_id, "chapter_count": t.chapter_count,
                         "name": t.name}
                        for t in book.translations
                    ],
                }
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            # Never expose credentials, upstream URLs or exception internals.
            raise HTTPException(status_code=502, detail="Failed to fetch book metadata") from exc

    @app.get("/api/books/chapters")
    def book_chapters(reference: str = Query(min_length=1, max_length=2048),
                      branch_id: int | None = None):
        try:
            with downloader_factory() as downloader:
                book = downloader.get_book(reference)
                if branch_id is not None and book.translations and not any(
                    t.branch_id == branch_id for t in book.translations
                ):
                    raise ValueError(f"Translation branch {branch_id} is not available")
                return {
                    "book_id": book.id,
                    "branch_id": branch_id,
                    "chapters": list(book.list_chapters(branch_id=branch_id)),
                }
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Failed to fetch chapter index") from exc

    def run_job(job_id: str, request: DownloadRequest):
        with lock:
            job = jobs[job_id]
            job.state = "running"

        def progress(current: int, total: int, message: str):
            with lock:
                job.current, job.total, job.message = current, total, message

        try:
            base.mkdir(parents=True, exist_ok=True)
            target = base / f"{job_id}.{request.format}"
            with downloader_factory() as downloader:
                result = downloader.download(
                    request.reference, format=request.format, output=target,
                    branch_id=request.branch_id, limit=request.limit,
                    chapter_from=request.chapter_from, chapter_to=request.chapter_to,
                    chapter_start_id=request.chapter_start_id,
                    chapter_end_id=request.chapter_end_id,
                    resume=request.resume, progress=progress,
                    cache_dir=base / "cache",
                )
            result_path = Path(result).resolve()
            if result_path != target or not result_path.is_file():
                raise RuntimeError("Downloader did not produce the expected file")
            with lock:
                job.path = result_path
                job.filename = target.name
                job.state = "completed"
        except Exception:
            with lock:
                job.state = "failed"
                job.error = "Download failed; inspect server logs"

    @app.post("/api/downloads", status_code=202)
    def start_download(request: DownloadRequest):
        if request.format not in FORMATS:
            raise HTTPException(status_code=422, detail="Unsupported export format")
        with lock:
            if len(jobs) >= max_jobs:
                raise HTTPException(status_code=429, detail="Download job capacity reached")
            job_id = uuid4().hex
            jobs[job_id] = Job(id=job_id, format=request.format)
        try:
            executor.submit(run_job, job_id, request)
        except RuntimeError as exc:
            with lock:
                jobs.pop(job_id, None)
            raise HTTPException(status_code=503, detail="Downloader is shutting down") from exc
        return snapshot(job_id)

    @app.get("/api/downloads/{job_id}")
    def get_download(job_id: str):
        return snapshot(job_id)

    @app.get("/api/downloads/{job_id}/file")
    def get_download_file(job_id: str):
        with lock:
            job = jobs.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Unknown download")
            if job.state != "completed" or job.path is None:
                raise HTTPException(status_code=409, detail="Download not completed")
            path = job.path
        if not path.is_file():
            raise HTTPException(status_code=410, detail="Download file no longer exists")
        return FileResponse(path, filename=path.name, media_type="application/octet-stream")

    return app


app = create_app()
