from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def is_frozen() -> bool:
    """Return whether a freezer is running the application."""
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """Locate read-only resources without creating directories."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
    return Path(__file__).resolve().parent.parent


def safe_join(root: Path, *parts: str) -> Path:
    """Reject absolute, Windows special, traversal and symlink escape paths."""
    for part in parts:
        if not isinstance(part, str) or not part or "\\" in part or ":" in part or "\x00" in part:
            raise ValueError("Invalid path part")
        components = part.split("/")
        reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
        if any(any(ord(ch) < 32 or ch in '<>"|?*' for ch in component) or component.split(".")[0].upper() in reserved for component in components):
            raise ValueError("Invalid Windows filename")
        if Path(part).is_absolute() or any(p in {"", ".", ".."} or p.endswith((" ", ".")) for p in part.split("/")):
            raise ValueError("Path must be a relative child path")
    target = root.joinpath(*parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("Path escapes its root")
    return target


def _user_root() -> Path:
    """Compute the default without import-time filesystem writes."""
    local = os.environ.get("LOCALAPPDATA", "").strip()
    base = Path(local).expanduser() if local else Path.home() / "AppData" / "Local"
    if not base.is_absolute():
        base = Path.home() / "AppData" / "Local"
    return base / "Dugout Atlas"


def ensure_directory(path: Path) -> Path:
    """Create parents safely and report access failures without private paths."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        LOGGER.error("Cannot create application data directory")
        raise
    return path


def resource_path(*parts: str) -> Path:
    """Locate a packaged read-only resource."""
    return safe_join(bundle_dir(), *parts)


def user_data_dir() -> Path:
    """Create and return the per-user application root."""
    return ensure_directory(_user_root())


def data_path(*parts: str, create_parent: bool = True) -> Path:
    """Locate a user file; validate before performing filesystem writes."""
    path = safe_join(_user_root(), *parts)
    if create_parent:
        ensure_directory(path.parent if parts else path)
    return path


def cache_dir() -> Path:
    return ensure_directory(data_path("cache"))


def database_dir() -> Path:
    return ensure_directory(data_path("database"))


def logs_dir() -> Path:
    return ensure_directory(data_path("logs"))


def exports_dir() -> Path:
    return ensure_directory(data_path("exports"))
