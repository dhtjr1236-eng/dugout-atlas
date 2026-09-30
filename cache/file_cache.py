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


class HeadshotCache:
    """ID-keyed headshots separate from the general files cache."""

    def __init__(self, root: Path = CACHE_DIR) -> None:
        self.root = Path(root) / 'headshots'

    def path_for(self, mlbam_id: int) -> Path:
        if type(mlbam_id) is not int or mlbam_id <= 0:
            raise ValueError('A positive MLBAM ID is required')
        return self.root / f'{mlbam_id}.png'

    def write(self, mlbam_id: int, data: bytes) -> None:
        """Atomically replace a validated download; concurrent readers see complete files."""
        import os
        import tempfile
        path = self.path_for(mlbam_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
