"""Environment variable helpers used across the automation package."""
from __future__ import annotations

import os
from typing import Optional

__all__ = ["_env"]


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Return the stripped environment variable or ``default`` when empty."""
    value = os.getenv(name)
    if value is None or str(value).strip() == "":
        return default
    return value
