"""Desktop assets that work both from source and a PyInstaller bundle."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon


def asset_path(name: str) -> Path:
    """Resolve an asset copied to a bundle root, with a source/install fallback."""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        bundled = Path(bundle_root) / name
        if bundled.is_file():
            return bundled
    return Path(__file__).resolve().parent / "assets" / name


def application_icon() -> QIcon:
    # ICO avoids relying on the SVG image plugin in a frozen Windows build and
    # contains the small sizes used by the notification area.
    return QIcon(str(asset_path("ranobe.ico")))
