"""Persistent default settings shared by downloader interfaces."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path


@dataclass
class DownloaderSettings:
    format: str = "epub"
    output_dir: str = "output"
    cache_dir: str = "output/.cache"
    resume: bool = False
    delay: float = 1.0
    retries: int = 5
    image_mode: str = "original"
    image_quality: int = 85
    image_max_width: int = 1600
    branch_id: int | None = None
    limit: int | None = None

    @classmethod
    def default_path(cls) -> Path:
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        return config_home / "ranobe-downloader" / "settings.json"

    @classmethod
    def load(cls, path: str | Path | None = None) -> "DownloaderSettings":
        config_path = Path(path) if path is not None else cls.default_path()
        if not config_path.is_file():
            return cls()
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot read downloader settings: {config_path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("Downloader settings must be a JSON object")
        known = {key: value for key, value in data.items() if key in cls.__dataclass_fields__}
        settings = cls(**known)
        settings.validate()
        return settings

    def save(self, path: str | Path | None = None) -> Path:
        self.validate()
        config_path = Path(path) if path is not None else self.default_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return config_path

    def validate(self) -> None:
        if self.format not in ("epub", "txt", "html"):
            raise ValueError("format must be epub, txt or html")
        if self.delay < 0 or self.retries < 1:
            raise ValueError("delay must be non-negative and retries must be positive")
        if self.image_mode not in ("original", "optimized") or not 1 <= self.image_quality <= 100 or self.image_max_width < 1:
            raise ValueError("Invalid image optimization settings")
        if self.limit is not None and self.limit < 1:
            raise ValueError("limit must be positive")
