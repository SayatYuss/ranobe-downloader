"""Atomic output replacement: preserve previous output until writing succeeds."""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterator


@contextmanager
def atomic_destination(destination: str | Path) -> Iterator[Path]:
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(dir=target.parent, prefix="." + target.name + "-",
                                suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
        yield temporary
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
