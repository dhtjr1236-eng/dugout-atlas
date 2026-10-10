"""Cumulative regular-season OPS from MLB game counts, never averaged ratios."""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Callable

from database.sqlite_manager import SQLiteManager
from services.base_http import sync_get_text
from services.freshness import source_ttl_days
from services.season_race import RaceError, RacePlayer, RaceService, SeasonAxis, sample_dates

LOGGER = logging.getLogger(__name__)
SOURCE = 'mlb_ops_game_log_v1'
LIMIT = 1000
FIELDS = ('atBats', 'hits', 'baseOnBalls', 'hitByPitch', 'sacFlies', 'totalBases', 'plateAppearances')


@dataclass(frozen=True)
class OpsPoint:
    day: str
    value: float
    fetched_at: str
    pa: int
    obp: float
    slg: float
    last_game: str


@dataclass(frozen=True)
class OpsResult:
    axis: SeasonAxis
    players: tuple[RacePlayer, ...]
    points: tuple[dict[str, OpsPoint], ...]
    requests: int
    cache_hits: int

    def sampled(self, mode: str, start: str | None = None,
                end: str | None = None) -> tuple[SeasonAxis, list[dict[str, OpsPoint]]]:
        """Select endpoints only; cumulative counts always begin with the season."""
        days = sample_dates(self.axis, mode, start, end)
        return (SeasonAxis(self.axis.season, self.axis.start, self.axis.end, days),
                [{day: points[day] for day in days if day in points} for points in self.points])


def completed_schedule(payload: dict, season: int, today: date) -> tuple[SeasonAxis, dict[int, str]]:
    """Use MLB official dates; exclude today and dates with unfinished fixtures."""
    buckets: dict[str, list[dict]] = {}
    for bucket in payload.get('dates', []):
        for game in bucket.get('games', []):
            if (game.get('gameType') != 'R' or
                    game.get('status', {}).get('detailedState') in {'Postponed', 'Cancelled'}):
                continue
            day = game.get('officialDate', bucket.get('date', ''))
            try:
                parsed = date.fromisoformat(day)
            except (TypeError, ValueError):
                raise RaceError('Invalid MLB schedule.') from None
            if parsed.year == season and parsed < today:
                buckets.setdefault(day, []).append(game)
    complete: dict[int, str] = {}
    days = []
    for day, games in sorted(buckets.items()):
        finals = [g for g in games if g.get('status', {}).get('abstractGameState') == 'Final']
        pending = [g for g in games if g not in finals and
                   g.get('status', {}).get('detailedState') not in {'Postponed', 'Cancelled'}]
        if finals and not pending:
            days.append(day)
        for game in finals:
            pk = game.get('gamePk')
            if type(pk) is not int or pk <= 0 or (pk in complete and complete[pk] != day):
                raise RaceError('Invalid MLB schedule.')
            complete[pk] = day
    if not days:
        raise RaceError('No completed regular-season dates available.')
    return SeasonAxis(season, days[0], days[-1], tuple(days)), complete


def game_rows(payload: dict, player_id: int, season: int) -> list[dict]:
    """Require unambiguous player/season IDs and reject truncated responses."""
    blocks = payload.get('stats')
    if not isinstance(blocks, list):
        raise RaceError('Invalid MLB game log.')
    if not blocks:
        return []
    matching = [b for b in blocks if b.get('type', {}).get('displayName') == 'gameLog'
                and b.get('group', {}).get('displayName') == 'hitting']
    if len(matching) != 1:
        raise RaceError('Invalid MLB game log.')
    block = matching[0]
    rows = block.get('splits')
    if not isinstance(rows, list):
        raise RaceError('Invalid MLB game log.')
    total = block.get('totalSplits', len(rows))
    if type(total) is not int or total != len(rows) or len(rows) >= LIMIT:
        raise RaceError('Incomplete MLB game log; OPS was not calculated.')
    seen: dict[int, dict] = {}
    for row in rows:
        if (row.get('player', {}).get('id') != player_id or
                type(row.get('player', {}).get('id')) is not int or
                str(row.get('season')) != str(season) or row.get('gameType') != 'R'):
            raise RaceError('MLB player or season mismatch.')
        pk = row.get('game', {}).get('gamePk')
        if type(pk) is not int or pk <= 0:
            raise RaceError('Invalid MLB game log.')
        if pk in seen and seen[pk] != row:
            raise RaceError('Conflicting MLB game records.')
        seen[pk] = row
    return list(seen.values())


def cumulative_ops(rows: list[dict], axis: SeasonAxis, games: dict[int, str],
                   fetched_at: str) -> dict[str, OpsPoint]:
    """Sum AB/H/BB/HBP/SF/TB, then compute OBP + SLG for each complete date."""
    daily: dict[str, list[dict]] = {}
    seen = set()
    for row in rows:
        pk = row['game']['gamePk']
        if pk not in games or pk in seen:
            continue
        seen.add(pk)
        daily.setdefault(games[pk], []).append(row['stat'])
    totals = dict.fromkeys(FIELDS, 0)
    points = {}
    last_game = ''
    for day in sorted(set(axis.dates) | set(daily)):
        for stat in daily.get(day, []):
            counts = {}
            for field in FIELDS:
                raw = stat.get(field)
                if isinstance(raw, str) and raw.isascii() and raw.isdecimal():
                    raw = int(raw)
                if type(raw) is not int or raw < 0:
                    raise RaceError('Missing or invalid batting counts; OPS was not calculated.')
                counts[field] = raw
            ab, h, bb, hbp, sf, tb, pa = (counts[f] for f in FIELDS)
            if h > ab or not h <= tb <= 4*h or ab+bb+hbp+sf > pa:
                raise RaceError('Missing or invalid batting counts; OPS was not calculated.')
            for field in FIELDS:
                totals[field] += counts[field]
            last_game = day
        ab, h, bb, hbp, sf, tb, pa = (totals[f] for f in FIELDS)
        denominator = ab + bb + hbp + sf
        if day in axis.dates and ab and denominator:
            obp, slg = (h + bb + hbp) / denominator, tb / ab
            points[day] = OpsPoint(day, obp+slg, fetched_at, pa, obp, slg, last_game)
    return points


class OpsRaceService:
    """At most one schedule and one game-log request per uncached player."""

    def __init__(self, db: SQLiteManager) -> None:
        self.db = db
        self._schedule_cache: dict[int, tuple[float, dict]] = {}

    @staticmethod
    def _get(url: str, params: dict, cancel: threading.Event) -> dict:
        RaceService.check(cancel)
        payload = json.loads(sync_get_text(url, params=params, retries=1))
        RaceService.check(cancel)
        if not isinstance(payload, dict):
            raise RaceError('Invalid MLB game log.')
        return payload

    def load(self, players: list[RacePlayer], season: int, cancel: threading.Event,
             emit: Callable[[dict], None]) -> OpsResult:
        if len(players) != 2 or any(p.role != 'bat' or type(p.mlbam_id) is not int
                                     or p.mlbam_id <= 0 for p in players):
            raise RaceError('OPS requires two batting roles.')
        today = datetime.now(UTC).date()
        ttl = source_ttl_days(season)
        requests = hits = 0
        RaceService.check(cancel)
        emit({'kind': 'ops_status', 'text': 'Checking completed MLB games…'})
        cached_schedule = self._schedule_cache.get(season)
        if cached_schedule and time.monotonic() - cached_schedule[0] < ttl*86400:
            payload = cached_schedule[1]
        else:
            payload = self._get('https://statsapi.mlb.com/api/v1/schedule', {
                'sportId': 1, 'season': season, 'gameType': 'R',
                'fields': 'dates,date,games,gamePk,gameType,officialDate,status,abstractGameState,detailedState',
            }, cancel)
            requests += 1
            self._schedule_cache[season] = (time.monotonic(), payload)
        axis, games = completed_schedule(payload, season, today)
        series = []
        for player in players:
            RaceService.check(cancel)
            emit({'kind': 'ops_status', 'text': 'Loading MLB batting game logs…'})
            cached = self.db.get_player_stats(player.mlbam_id, SOURCE, season, 'bat:R', ttl)
            rows = None
            if cached:
                try:
                    if (cached['mlbam_id'] != player.mlbam_id or cached['season'] != season
                            or cached['cutoff'] != axis.end):
                        raise ValueError('Cache identity mismatch')
                    rows = game_rows(cached['payload'], player.mlbam_id, season)
                    stamp = cached['fetched_at']
                except (KeyError, TypeError, ValueError, RaceError):
                    LOGGER.warning('Invalid OPS game-log cache; fetching a fresh copy')
                    rows = None
            if rows is None:
                payload = self._get(f'https://statsapi.mlb.com/api/v1/people/{player.mlbam_id}/stats', {
                    'stats': 'gameLog', 'group': 'hitting', 'season': season,
                    'gameType': 'R', 'limit': LIMIT,
                }, cancel)
                requests += 1
                rows = game_rows(payload, player.mlbam_id, season)
                stamp = datetime.now(UTC).isoformat(timespec='seconds')
                # Validate counts before persisting any newly fetched result.
                points = cumulative_ops(rows, axis, games, stamp)
                RaceService.check(cancel)
                self.db.set_player_stats(player.mlbam_id, SOURCE, season, 'bat:R', {
                    'mlbam_id': player.mlbam_id, 'season': season, 'payload': payload, 'fetched_at': stamp, 'cutoff': axis.end,
                })
            else:
                hits += 1
                points = cumulative_ops(rows, axis, games, stamp)
            series.append(points)
        RaceService.check(cancel)
        emit({'kind': 'ops_status', 'text': 'Calculating cumulative OPS…'})
        return OpsResult(axis, tuple(players), tuple(series), requests, hits)
