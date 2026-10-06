from __future__ import annotations

import hashlib
import json
import logging
from config.paths import safe_join, ensure_directory
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from config.settings import CACHE_DIR


class JsonCache:
    """Small disk cache used for expensive non-live source responses."""

    def __init__(self, root: Path = CACHE_DIR) -> None:
        self.root = Path(root) / "json"
        ensure_directory(self.root)

    def _path(self, namespace: str, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        directory = safe_join(self.root, namespace)
        ensure_directory(directory)
        return directory / f"{digest}.json"

    def get(self, namespace: str, key: str, ttl_days: int) -> Any | None:
        path = self._path(namespace, key)
        if not path.exists():
            return None
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        if datetime.now(UTC) - modified >= timedelta(days=ttl_days):
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logging.getLogger(__name__).warning("Cannot read or decode JSON cache")
            return None

    def set(self, namespace: str, key: str, value: Any) -> Path:
        path = self._path(namespace, key)
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(
                json.dumps(value, ensure_ascii=False, default=str), encoding="utf-8"
            )
            tmp.replace(path)
        except OSError:
            logging.getLogger(__name__).warning("Cannot write JSON cache")
            raise
        return path
