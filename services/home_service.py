from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from config.settings import DATA_DIR
from database.sqlite_manager import SQLiteManager


@dataclass(frozen=True)
class RecapMetric:
    name: str
    current: float | None
    previous: float | None

    @property
    def delta(self) -> float | None:
        if self.current is None or self.previous is None:
            return None
        return self.current - self.previous


@dataclass(frozen=True)
class SeasonRecap:
    player_id: int
    name: str
    role: str
    metrics: tuple[RecapMetric, ...]
    current_updated_at: str = ''
    previous_updated_at: str = ''


def _recap_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _load_recaps(connection, favorites: list[dict], season: int) -> tuple[SeasonRecap, ...]:
    # Exact annual roles exclude monthly/daily/history and all other providers.
    # Historical cache is intentionally readable after TTL; the UI labels it saved data.
    from services.fangraphs_service import FG_CACHE_SOURCE

    recaps = []
    for favorite in favorites:
        saved = {}
        records = connection.execute(
            '''SELECT season, role, data_json, updated_at FROM player_stats
               WHERE player_id=? AND source=? AND season IN (?, ?)
               AND role IN ('batter', 'pitcher')''',
            (favorite['id'], FG_CACHE_SOURCE, season, season - 1),
        ).fetchall()
        for record in records:
            try:
                payload = json.loads(record['data_json'])
            except (TypeError, ValueError):
                continue
            if isinstance(payload, dict):
                saved[(record['season'], record['role'])] = (payload, record['updated_at'])
        roles = [role for role in ('batter', 'pitcher') if any(key[1] == role for key in saved)]
        if not roles:
            roles = ['pitcher' if favorite['position'].upper() in {'P', 'SP', 'RP'} else 'batter']
        for role in roles:
            current, current_at = saved.get((season, role), ({}, ''))
            previous, previous_at = saved.get((season - 1, role), ({}, ''))
            names = ('ERA', 'K%', 'fWAR') if role == 'pitcher' else ('OPS', 'HR', 'fWAR')
            recaps.append(SeasonRecap(
                favorite['id'], favorite['name'], role,
                tuple(RecapMetric(name, _recap_number(current.get(name)),
                                 _recap_number(previous.get(name))) for name in names),
                current_at, previous_at,
            ))
    return tuple(recaps)


@dataclass(frozen=True)
class HomeSnapshot:
    """Local inventory and saved season comparisons, without a freshness guarantee."""
    season: int
    favorites: tuple[dict, ...]
    player_count: int
    source_count: int
    record_count: int
    updated_at: str
    recaps: tuple[SeasonRecap, ...] = ()


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
                         'team': str(row.get('team') or ''),
                         'position': str(row.get('position') or '')})
    with db.connection() as connection:
        summary = connection.execute('''SELECT COUNT(*) AS records,
            COUNT(DISTINCT player_id) AS players, COUNT(DISTINCT source) AS sources,
            MAX(updated_at) AS updated FROM player_stats WHERE season=?''', (season,)).fetchone()
        recaps = _load_recaps(connection, rows, season)
    return HomeSnapshot(season, tuple(rows), summary['players'], summary['sources'],
                        summary['records'], summary['updated'] or '', recaps)
