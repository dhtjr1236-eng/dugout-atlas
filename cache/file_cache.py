from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from config.settings import CACHE_DIR


class FileCache:
    def __init__(self, root: Path = CACHE_DIR) -> None:
        self.root = Path(root) / "files"
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, namespace: str, filename: str) -> Path:
        directory = self.root / namespace
        directory.mkdir(parents=True, exist_ok=True)
        safe = "".join(ch for ch in filename if ch.isalnum() or ch in "._-")
        return directory / safe

    @staticmethod
    def is_fresh(path: Path, ttl_days: int) -> bool:
        if not path.exists():
            return False
        stamp = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        return datetime.now(UTC) - stamp < timedelta(days=ttl_days)
