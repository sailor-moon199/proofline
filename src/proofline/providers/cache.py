"""Disk-backed cache layer for LLM responses."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DiskCache:
    """Persist provider responses to disk keyed by a stable hash."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)

    def get(self, key: str) -> Any | None:
        """Return cached payload if present; otherwise None."""
        path = self._path_for(key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, key: str, value: Any) -> None:
        """Write a JSON payload for a cache key."""
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True), encoding="utf-8")

    def _path_for(self, key: str) -> Path:
        return self.root_dir / f"{key}.json"
