from __future__ import annotations

import json
import platform
import shutil
import sys
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from config.settings import CACHE_DIR, DATA_DIR, RUNTIME_ROOT, SETTINGS

SOURCES = ('MLB', 'FanGraphs', 'Baseball-Reference', 'Savant')


def clear_cache(db, source: str | None = None) -> int:
    """Delete disposable caches only. Caller must first wait for active jobs."""
    if source is not None and source not in SOURCES:
        raise ValueError('Unknown source')
    count = 0
    with db.connection() as connection:
        rows = connection.execute('SELECT DISTINCT source, role FROM player_stats').fetchall()
        for row in rows:
            name, role = row['source'], row['role']
            matches = source is None or (
                source == 'FanGraphs' and (name.startswith('fangraphs') or (name == 'running_metrics_v1' and role != 'sprint_speed'))
                or source == 'Baseball-Reference' and name.startswith(('bref', 'baseball_reference'))
                or source == 'Savant' and (name.startswith('statcast') or name == 'running_metrics_v1' and role == 'sprint_speed')
            )
            if matches:
                count += connection.execute('DELETE FROM player_stats WHERE source=? AND role=?', (name, role)).rowcount
        if source in (None, 'Savant'):
            count += connection.execute('DELETE FROM pitch_stats').rowcount
        if source in (None, 'MLB'):
            count += connection.execute('DELETE FROM games').rowcount
            count += connection.execute('DELETE FROM team_cache').rowcount
            count += connection.execute('DELETE FROM players').rowcount
    # CACHE_DIR also contains Python source in legacy installs. Never remove it.
    folders = []
    if source in (None, 'Savant'):
        folders.append(CACHE_DIR / 'json')
    if source in (None, 'MLB'):
        folders.append(CACHE_DIR / 'files')
    for folder in folders:
        if folder.is_dir() and not folder.is_symlink():
            shutil.rmtree(folder)
    if source in (None, 'MLB'):
        from services.player_enhancements import _ROSTER_CACHE
        _ROSTER_CACHE.clear()
    if source in (None, 'FanGraphs', 'Savant'):
        from services.compare_league_context import _CACHE, _LOCK
        with _LOCK:
            _CACHE.clear()
    if source in (None, 'Baseball-Reference'):
        from services.bref_service import BaseballReferenceService
        with BaseballReferenceService._daily_cache_lock:
            BaseballReferenceService._daily_cache.clear()
        # Deliberately retain the provider's 403/429 circuit breaker.
    return count


def copy_data_location(destination: str, db) -> str:
    """Copy durable data to an empty root; SQLite backup includes committed WAL."""
    target = Path(destination).expanduser().resolve()
    current = RUNTIME_ROOT.resolve()
    if target == current:
        return str(target)
    if current in target.parents or target in current.parents:
        raise ValueError('Choose an empty folder outside the current data folder.')
    if target.exists() and any(target.iterdir()):
        raise ValueError('Choose an empty folder outside the current data folder.')
    target.mkdir(parents=True, exist_ok=True)
    data = target / 'data'
    data.mkdir()
    try:
        for item in DATA_DIR.iterdir():
            if item.is_symlink() or item.name in {db.db_path.name, db.db_path.name + '-wal', db.db_path.name + '-shm'}:
                continue
            if item.is_dir():
                # Reject links in imported data rather than following them elsewhere.
                if any(child.is_symlink() for child in item.rglob('*')):
                    raise ValueError('Data contains symbolic links')
                shutil.copytree(item, data / item.name)
            elif item.is_file():
                shutil.copy2(item, data / item.name)
        import sqlite3
        with db.connection() as source, sqlite3.connect(data / db.db_path.name) as output:
            source.backup(output)
    except Exception:
        shutil.rmtree(data)
        raise
    return str(target)


def diagnostics(db, preferences: dict) -> dict:
    dependencies = {}
    for name in ('PyQt6', 'requests', 'aiohttp', 'pandas', 'pybaseball'):
        try:
            dependencies[name] = version(name)
        except PackageNotFoundError:
            dependencies[name] = 'not installed'
    with db.connection() as connection:
        sources = [dict(row) for row in connection.execute(
            'SELECT source, COUNT(*) AS cached_rows, MAX(updated_at) AS last_cached_at FROM player_stats GROUP BY source'
        )]
    return {
        'app': SETTINGS.app_name, 'version': SETTINGS.app_version,
        'created_at': datetime.now(UTC).isoformat(),
        'os': platform.system(), 'os_release': platform.release(),
        'python': sys.version.split()[0], 'dependencies': dependencies,
        'settings': {key: value for key, value in preferences.items() if key != 'data_root'},
        'source_cache': sources,
        'privacy': 'No paths, player searches, logs, credentials or imported file contents included.',
    }


def export_diagnostics(path: str, db, preferences: dict) -> None:
    Path(path).write_text(json.dumps(diagnostics(db, preferences), ensure_ascii=False, indent=2), encoding='utf-8')
