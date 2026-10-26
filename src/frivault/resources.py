"""Resolve bundled resources in source and PyInstaller builds."""

from __future__ import annotations

import sys
from pathlib import Path


def resource_path(*parts: str) -> Path:
    """Return a path under the packaged resources directory.

    PyInstaller extracts bundled data under ``sys._MEIPASS``. In a source
    checkout, resources live alongside this Python package.
    """

    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root is not None:
        root = Path(bundle_root) / "frivault" / "resources"
    else:
        root = Path(__file__).resolve().parent / "resources"
    return root.joinpath(*parts)
