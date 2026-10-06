from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from config.settings import DATA_DIR
from database.sqlite_manager import SQLiteManager


@dataclass(frozen=True)
class HomeSnapshot:
    """Local inventory, not derived season statistics or a freshness guarantee."""
    season: int
    favorites: tuple[dict, ...]
    player_count: int
    source_count: int
    record_count: int
    updated_at: str


def load_home_snapshot(db: SQLiteManager, season: int, favorites_path: Path | None = None) -> HomeSnapshot:
    """Read bounded metadata and favorites in a worker, without external requests."""
    path = favorites_path if favorites_path is not None else DATA_DIR / 'favorites.json'
    rows = []
    if path.exists():
        payload = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(payload, dict) or not isinstance(payload.get('players', []), list):
            raise ValueError('Invalid favorites data')
        seen = set()
        for row in payload.get('players', []):
            if not isinstance(row, dict):
                continue
            player_id = row.get('id')
            if type(player_id) is not int or player_id <= 0 or player_id in seen:
                continue
            seen.add(player_id)
            rows.append({'id': player_id, 'name': str(row.get('name') or player_id),
                         'team': str(row.get('team') or '')})
    with db.connection() as connection:
        summary = connection.execute('''SELECT COUNT(*) AS records,
            COUNT(DISTINCT player_id) AS players, COUNT(DISTINCT source) AS sources,
            MAX(updated_at) AS updated FROM player_stats WHERE season=?''', (season,)).fetchone()
    return HomeSnapshot(season, tuple(rows), summary['players'], summary['sources'],
                        summary['records'], summary['updated'] or '')
