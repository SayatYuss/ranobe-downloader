"""Persistent desktop state: preferences, completed downloads and logging."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime, timezone

from PySide6.QtCore import QStandardPaths

APP_NAME = "RanobeDownloader"


def app_data() -> Path:
    path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    result = Path(path) if path else Path.home() / ".local" / "share" / APP_NAME
    result.mkdir(parents=True, exist_ok=True)
    return result


def downloads_dir() -> Path:
    raw = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
    return Path(raw) if raw else Path.home() / "Downloads"


class Store:
    def __init__(self, root: Path | None = None):
        self.root = root or app_data()
        self.root.mkdir(parents=True, exist_ok=True)
        self.cache = self.root / "cache"
        self.cache.mkdir(exist_ok=True)
        self.settings_file = self.root / "settings.json"
        self.history_file = self.root / "history.json"
        self.settings = self._read(self.settings_file, {"directory": str(downloads_dir()), "theme": "system"})
        self.history = self._read(self.history_file, [])
        if not isinstance(self.settings, dict):
            self.settings = {"directory": str(downloads_dir()), "theme": "system"}
        if not isinstance(self.history, list):
            self.history = []

    @staticmethod
    def _read(path: Path, fallback):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return fallback

    @staticmethod
    def _write(path: Path, value):
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def save_settings(self):
        self._write(self.settings_file, self.settings)

    def add_download(self, *, title: str, path: Path, fmt: str):
        record = {
            "title": title, "path": str(path), "format": fmt,
            "size": path.stat().st_size if path.exists() else 0,
            "date": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        }
        self.history.insert(0, record)
        self._write(self.history_file, self.history)


def configure_logging(root: Path):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(root / "desktop.log", encoding="utf-8")],
    )
