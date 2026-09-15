from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    if is_frozen() and getattr(sys, "_MEIPASS", None):
        return Path(str(sys._MEIPASS)).resolve()
    return Path(__file__).resolve().parents[1]


def resource_path(*parts: str) -> Path:
    return bundle_root().joinpath(*parts)


def frozen_engine_executable() -> Path:
    """Return the sibling console runner used by a frozen GUI build."""
    return Path(sys.executable).resolve().with_name("FutureEPWEngine.exe")
