"""Provider-returned cumulative fWAR only; no game-WAR sums or synthetic points."""
from __future__ import annotations

import json
import math
import threading
import time
from dataclasses import asdict, dataclass, replace
from datetime import UTC, date, datetime, timedelta
from typing import Callable

from services.base_http import sync_get_text
from services.fangraphs_service import FG_LEADERS_URL, FanGraphsService

SOURCE = 'fangraphs_race_v1'
FOG_DRAWDOWN = 0.5
REQUEST_INTERVAL = 1.0
_SCHEDULE_FIELDS = 'dates,date,games,gamePk,gameType,gameDate,officialDate,status,abstractGameState,detailedState'
_REQUEST_LOCK = threading.Lock()
_BLOCKED_UNTIL = 0.0


class RaceError(RuntimeError):
    pass


class Cancelled(RaceError):
    pass


@dataclass(frozen=True)
class RacePlayer:
    mlbam_id: int
    name: str
    role: str
    fg_id: int | None = None

    def __post_init__(self):
        if self.role not in {'bat', 'pit'}:
            raise RaceError('Select batting or pitching explicitly.')
        if self.mlbam_id <= 0 or (self.fg_id is not None and self.fg_id <= 0):
            raise RaceError('FanGraphs ID mapping failed')


@dataclass(frozen=True)
class SeasonAxis:
    season: int
    start: str
    end: str
    dates: tuple[str, ...]


@dataclass(frozen=True)
class Point:
    day: str
    war: float
    fetched_at: str

    @property
    def value(self) -> float:
        """Metric-neutral value for shared race rendering; WAR cache stays unchanged."""
        return self.war


def season_axis(payload: dict, season: int, today: date | None = None) -> SeasonAxis:
    """Use the literal calendar portion of MLB gameDate; never localize timestamps.

    Only complete dates before today are sampled. This conservative cutoff avoids
    mixing a completed afternoon game with an unfinished evening game.
    """
    today = today or datetime.now(UTC).date()
    games: dict[str, list[dict]] = {}
    for bucket in payload.get('dates', []):
        for game in bucket.get('games', []):
            if game.get('gameType') != 'R':
                continue
            raw = str(game.get('gameDate', ''))[:10]
            try:
                d = date.fromisoformat(raw)
            except ValueError:
                continue
            if d.year == season:
                games.setdefault(raw, []).append(game)
    if not games:
        raise RaceError('No regular-season schedule available.')
    dates = sorted(games)
    complete = []
    for day in dates:
        if day >= today.isoformat():
            continue
        group = games[day]
        # Postponed/cancelled fixtures do not hold up a completed calendar day.
        final = [g for g in group if g.get('status', {}).get('abstractGameState') == 'Final']
        pending = [g for g in group if g not in final and g.get('status', {}).get('detailedState') not in {'Postponed', 'Cancelled'}]
        if final and not pending:
            complete.append(day)
    return SeasonAxis(season, dates[0], dates[-1], tuple(complete))


def sample_dates(axis: SeasonAxis, preview: bool | str = "weekly",
                 start: str | None = None, end: str | None = None) -> tuple[str, ...]:
    """Select real completed dates; range filters never reset cumulative WAR start."""
    mode = ('weekly' if preview else 'full') if isinstance(preview, bool) else preview.lower()
    days = tuple(d for d in axis.dates if (start is None or d >= start) and (end is None or d <= end))
    if start and end and start > end:
        raise RaceError('Start date must precede end date.')
    if mode not in {'monthly', 'bi-weekly', 'weekly', 'preview', 'full', 'range'}:
        raise RaceError('Unknown sampling mode.')
    if len(days) < 2 or mode in {'full', 'range'}:
        return days
    if mode == 'monthly':
        months = {d[:7]: d for d in days}
        return tuple(months.values())
    if mode in {'weekly', 'preview'}:
        return tuple(dict.fromkeys((*days[::7], days[-1])))
    selected = [days[0]]
    for day in days[1:]:
        if (date.fromisoformat(day) - date.fromisoformat(selected[-1])).days >= 14:
            selected.append(day)
    return tuple(dict.fromkeys((*selected, days[-1])))


@dataclass(frozen=True)
class RacePlan:
    """Snapshot of cached points approved before any range requests begin."""
    axis: SeasonAxis
    players: tuple[RacePlayer, ...]
    jobs: tuple[tuple[RacePlayer, str, Point | None], ...]
    interval: float

    @property
    def total_jobs(self) -> int:
        return len(self.jobs)

    @property
    def cache_hits(self) -> int:
        return sum(point is not None for _, _, point in self.jobs)

    @property
    def new_jobs(self) -> int:
        return self.total_jobs - self.cache_hits

    @property
    def estimated_seconds(self) -> float:
        return self.new_jobs * self.interval

    def message(self) -> dict:
        return {'kind': 'plan', 'axis': self.axis, 'players': list(self.players),
                'total': self.total_jobs, 'hits': self.cache_hits, 'new': self.new_jobs,
                'estimated_seconds': self.estimated_seconds}


def strict_row(rows: list[dict], player: RacePlayer) -> dict | None:
    """MLBAM required for initial mapping; a verified FG ID can match later rows.

    Conflicting identifiers and duplicate team splits are rejected, never summed.
    """
    def ident(row, keys):
        for key in keys:
            value = row.get(key)
            if value not in (None, ''):
                try:
                    number = float(value)
                    return int(number) if math.isfinite(number) and number.is_integer() else -1
                except (TypeError, ValueError):
                    return -1
        return None
    found = []
    for row in rows:
        mid = ident(row, ('xMLBAMID', 'MLBAMID', 'mlbam_id', 'key_mlbam'))
        fid = ident(row, ('playerid', 'IDfg', 'PlayerId'))
        if mid == player.mlbam_id or (player.fg_id is not None and fid == player.fg_id):
            if mid is not None and mid != player.mlbam_id:
                raise RaceError('FanGraphs ID mismatch')
            if fid is None or fid <= 0 or (player.fg_id is not None and fid != player.fg_id):
                raise RaceError('FanGraphs ID mismatch')
            found.append(row)
    if len(found) > 1:
        raise RaceError('Ambiguous FanGraphs rows; team splits are not summed.')
    return found[0] if found else None


def point_from_row(row: dict, day: str, fetched_at: str) -> Point:
    value = row.get('WAR')
    if isinstance(value, bool) or value in (None, ''):
        raise RaceError('Missing WAR field')
    try:
        war = float(value)
    except (TypeError, ValueError) as exc:
        raise RaceError('Invalid WAR field') from exc
    if not math.isfinite(war):
        raise RaceError('Invalid WAR field')
    return Point(day, war, fetched_at)


def peak(points: dict[str, Point]) -> Point | None:
    ordered = sorted(points.values(), key=lambda p: p.day)
    return max(ordered, key=lambda p: p.war) if ordered else None


def drawdown(points: dict[str, Point], day: str) -> bool:
    current = points.get(day)
    ordered = sorted((p for p in points.values() if p.day <= day), key=lambda p: p.day)
    if current is None or len(ordered) < 2:
        return False
    local_peak = ordered[0].war
    for before, after in zip(ordered, ordered[1:]):
        if after.war > before.war:
            local_peak = after.war
    return local_peak - current.war >= FOG_DRAWDOWN


class RaceService:
    def __init__(self, fangraphs: FanGraphsService, interval: float = REQUEST_INTERVAL):
        self.fg = fangraphs
        self.db = fangraphs.db
        self.interval = interval

    @staticmethod
    def check(cancel: threading.Event):
        if cancel.is_set():
            raise Cancelled('Cancelled')

    def schedule(self, season: int, cancel: threading.Event) -> SeasonAxis:
        self.check(cancel)
        payload = json.loads(sync_get_text(
            'https://statsapi.mlb.com/api/v1/schedule',
            params={'sportId': 1, 'season': season, 'gameType': 'R', 'fields': _SCHEDULE_FIELDS},
            retries=1,
        ))
        self.check(cancel)
        return season_axis(payload, season)

    def _request(self, params: dict, cancel: threading.Event) -> dict:
        global _BLOCKED_UNTIL
        self.check(cancel)
        if time.monotonic() < _BLOCKED_UNTIL:
            raise RaceError('FanGraphs cooldown; try again later.')
        try:
            payload = self.fg._request_json(FG_LEADERS_URL, params)
        except Exception as exc:
            if '403' in str(exc) or '429' in str(exc):
                _BLOCKED_UNTIL = time.monotonic() + 60
            raise
        self.check(cancel)
        if cancel.wait(self.interval):
            raise Cancelled('Cancelled')
        if not isinstance(payload.get('data'), list):
            raise RaceError('Invalid FanGraphs data payload')
        return payload

    def resolve(self, player: RacePlayer, axis: SeasonAxis, cancel: threading.Event) -> RacePlayer:
        # Do not reuse the legacy name-fallback ID cache.
        with _REQUEST_LOCK:
            params = self.fg._api_params(axis.season, axis.season, player.role == 'pit', ind=0)
            row = strict_row(self._request(params, cancel)['data'], player)
        if row is None:
            raise RaceError('FanGraphs ID mapping failed')
        fid = next(row[k] for k in ('playerid', 'IDfg', 'PlayerId') if row.get(k) is not None)
        return replace(player, fg_id=int(float(fid)))

    @staticmethod
    def cache_role(player: RacePlayer, axis: SeasonAxis, day: str) -> str:
        return f'{player.role}:fg={player.fg_id}:start={axis.start}:end={day}:mode=range:api=v1'

    def cached(self, player: RacePlayer, axis: SeasonAxis, day: str) -> Point | None:
        raw = self.db.get_player_stats(player.mlbam_id, SOURCE, axis.season,
                                       self.cache_role(player, axis, day), self.fg._cache_ttl_days(axis.season))
        if not raw:
            return None
        try:
            if raw['day'] != day or raw['fg_id'] != player.fg_id or raw['mlbam_id'] != player.mlbam_id:
                return None
            return point_from_row({'WAR': raw['war']}, day, raw['fetched_at'])
        except (KeyError, TypeError, RaceError):
            return None

    def fetch(self, player: RacePlayer, axis: SeasonAxis, day: str, cancel: threading.Event) -> Point | None:
        if player.fg_id is None or day not in axis.dates:
            raise RaceError('Unverified player or date')
        # Global serial lock + second cache check deduplicates in-flight requests.
        with _REQUEST_LOCK:
            self.check(cancel)
            cached = self.cached(player, axis, day)
            if cached is not None:
                return cached
            params = self.fg._api_params(axis.season, axis.season, player.role == 'pit',
                                         start_date=axis.start, end_date=day, ind=0)
            row = strict_row(self._request(params, cancel)['data'], player)
            if row is None or row.get('WAR') in (None, ''):
                return None
            point = point_from_row(row, day, datetime.now(UTC).isoformat(timespec='seconds'))
            self.db.set_player_stats(player.mlbam_id, SOURCE, axis.season,
                                     self.cache_role(player, axis, day),
                                     {**asdict(point), 'fg_id': player.fg_id, 'mlbam_id': player.mlbam_id,
                                      'source': 'FanGraphs', 'params': params})
            return point

    def plan(self, players: list[RacePlayer], axis: SeasonAxis, mode: bool | str,
             start: str | None = None, end: str | None = None) -> RacePlan:
        """Local-only preflight; callers must supply strictly resolved IDs."""
        if any(p.fg_id is None for p in players):
            raise RaceError('Unverified player or date')
        days = sample_dates(axis, mode, start, end)
        if not days:
            raise RaceError('No completed regular-season dates available.')
        jobs = dict.fromkeys((p, day) for p in players for day in days)
        return RacePlan(axis, tuple(players),
                        tuple((p, d, self.cached(p, axis, d)) for p, d in jobs), self.interval)

    def prepare(self, players: list[RacePlayer], season: int, mode: bool | str,
                cancel: threading.Event, start: str | None = None,
                end: str | None = None) -> RacePlan:
        """Resolve schedule/IDs in a worker; never request date-range WAR here."""
        axis = self.schedule(season, cancel)
        resolved = [self.resolve(p, axis, cancel) for p in players]
        self.check(cancel)
        return self.plan(resolved, axis, mode, start, end)

    def execute(self, plan: RacePlan, cancel: threading.Event,
                emit: Callable[[dict], None]) -> SeasonAxis:
        """Execute an approved snapshot; cache expiration cannot increase its budget."""
        self.check(cancel)
        emit(plan.message())
        done = 0
        for player, day, point in plan.jobs:
            self.check(cancel)
            if point is None:
                point = self.fetch(player, plan.axis, day, cancel)
                done += 1
            emit({'kind': 'point', 'player': player, 'day': day, 'point': point,
                  'done': done, 'new': plan.new_jobs})
        return plan.axis

    def load(self, players: list[RacePlayer], season: int, preview: bool | str,
             cancel: threading.Event, emit: Callable[[dict], None]):
        """Compatibility entry point; interactive clients use prepare then execute."""
        return self.execute(self.prepare(players, season, preview, cancel), cancel, emit)


def demo_points(axis: SeasonAxis) -> list[dict[str, Point]]:
    """Sparse, explicit fictional fixture. Never passed to the real cache."""
    june = next((d for d in axis.dates if d[5:7] == '06'), None)
    sept = next((d for d in axis.dates if d[5:7] == '09'), None)
    if not june or not sept or not axis.dates:
        raise RaceError('Demo requires completed June and September dates.')
    days = [axis.dates[0], june, sept, axis.dates[-1]]
    return [{d: Point(d, war, 'DEMO') for d, war in zip(days, values)}
            for values in ([0.0, 1.8, 1.1, 0.9], [0.0, 1.2, 3.1, 2.8])]
