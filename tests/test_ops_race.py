from __future__ import annotations

import copy
import threading
from datetime import date
from types import SimpleNamespace

import pytest

from database.sqlite_manager import SQLiteManager
from services.ops_race import (FIELDS, SOURCE, OpsRaceService, OpsResult,
                               completed_schedule, cumulative_ops, game_rows)
from services.season_race import Cancelled, RaceError, RacePlayer, SeasonAxis


def fixture_row(pk=1, player=10, day='2025-04-01', **counts):
    stat = dict(zip(FIELDS, (4, 2, 1, 0, 0, 3, 5)))
    stat.update(counts)
    return {'season': '2025', 'gameType': 'R', 'player': {'id': player},
            'game': {'gamePk': pk}, 'date': day, 'stat': stat}


def payload(rows):
    return {'stats': [{'type': {'displayName': 'gameLog'},
                       'group': {'displayName': 'hitting'}, 'splits': rows}]}


def schedule():
    return {'dates': [{'date': f'2025-04-0{d}', 'games': [
        {'gamePk': d, 'gameType': 'R', 'officialDate': f'2025-04-0{d}',
         'status': {'abstractGameState': 'Final', 'detailedState': 'Final'}}
    ]} for d in range(1, 4)]}


def axis_games():
    return completed_schedule(schedule(), 2025, date(2025, 4, 4))


def test_ops_uses_counts_not_provider_ratios_or_averages():
    axis, games = axis_games()
    rows = [fixture_row(), fixture_row(2, atBats=1, hits=0, baseOnBalls=0,
                                      totalBases=0, plateAppearances=1, ops=99)]
    points = cumulative_ops(rows, axis, games, 'now')
    assert points['2025-04-01'].value == pytest.approx(3/5 + 3/4)
    final = points['2025-04-03']
    assert final.value == pytest.approx(3/6 + 3/5)
    assert final.pa == 6 and final.last_game == '2025-04-02'
    assert final.value != pytest.approx((1.35 + 0) / 2)


def test_doubleheader_both_games_and_duplicates_not_double_counted():
    axis, _ = axis_games()
    rows = game_rows(payload([fixture_row(), fixture_row(), fixture_row(2)]), 10, 2025)
    points = cumulative_ops(rows, axis, {1: axis.start, 2: axis.start}, 'now')
    assert points[axis.start].pa == 10
    assert points[axis.start].value == pytest.approx(1.35)


def test_sacrifice_hbp_and_ibb_semantics():
    axis, games = axis_games()
    row = fixture_row(hitByPitch=1, sacFlies=1, plateAppearances=9,
                      intentionalWalks=1, sacBunts=1, catchersInterference=1)
    p = cumulative_ops([row], axis, games, 'now')[axis.start]
    assert p.obp == pytest.approx(4/7)
    assert p.pa == 9 and p.slg == .75


@pytest.mark.parametrize('bad', [None, -1, True, 'nan', 1.5])
def test_missing_or_invalid_counts_fail_without_synthetic_ops(bad):
    axis, games = axis_games()
    with pytest.raises(RaceError, match='counts'):
        cumulative_ops([fixture_row(hits=bad)], axis, games, 'now')


def test_no_at_bats_and_no_game_logs_stay_empty():
    axis, games = axis_games()
    assert cumulative_ops([], axis, games, 'now') == {}
    row = fixture_row(atBats=0, hits=0, totalBases=0, plateAppearances=1)
    assert cumulative_ops([row], axis, games, 'now') == {}
    assert game_rows({'stats': []}, 10, 2025) == []


@pytest.mark.parametrize('change', [
    {'player': {'id': 11}}, {'player': {'id': True}}, {'season': '2024'}, {'gameType': 'W'},
])
def test_strict_identity_and_regular_season(change):
    row = fixture_row(); row.update(change)
    with pytest.raises(RaceError):
        game_rows(payload([row]), 10, 2025)


def test_conflicting_and_truncated_rows_rejected():
    with pytest.raises(RaceError):
        game_rows(payload([fixture_row(), fixture_row(hits=1)]), 10, 2025)
    data = payload([fixture_row()]); data['stats'][0]['totalSplits'] = 2
    with pytest.raises(RaceError, match='Incomplete'):
        game_rows(data, 10, 2025)


def test_official_dates_and_incomplete_day_do_not_drop_prior_final_game():
    data = schedule()
    data['dates'][0]['games'][0]['gameDate'] = '2025-04-02T02:00:00Z'
    data['dates'][0]['games'].append({'gamePk': 50, 'gameType': 'R',
        'officialDate': '2025-04-01', 'status': {'abstractGameState': 'Live'}})
    axis, games = completed_schedule(data, 2025, date(2025, 4, 3))
    assert axis.dates == ('2025-04-02',)
    assert games[1] == '2025-04-01' and 50 not in games and 3 not in games
    assert cumulative_ops([fixture_row()], axis, games, 'now')[axis.end].pa == 5


def test_range_is_endpoint_filter_not_new_cumulative_start():
    axis, games = axis_games()
    points = cumulative_ops([fixture_row(), fixture_row(2)], axis, games, 'now')
    result = OpsResult(axis, (), (points, points), 3, 0)
    filtered, series = result.sampled('full', '2025-04-02', '2025-04-02')
    assert filtered.dates == ('2025-04-02',) and series[0][filtered.dates[0]].pa == 10


def test_service_requests_are_bounded_and_cached(tmp_path, monkeypatch):
    service = OpsRaceService(SQLiteManager(tmp_path/'ops.db'))
    calls = []
    def fetch(url, params, cancel):
        calls.append(url)
        if url.endswith('schedule'):
            return schedule()
        pid = int(url.split('/people/')[1].split('/')[0])
        return payload([fixture_row(player=pid)])
    monkeypatch.setattr(service, '_get', fetch)
    players = [RacePlayer(10, 'A', 'bat'), RacePlayer(20, 'B', 'bat')]
    result = service.load(players, 2025, threading.Event(), lambda m: None)
    assert len(calls) == result.requests == 3 and result.cache_hits == 0
    for mode in ('monthly', 'weekly', 'full'):
        result.sampled(mode)
    second = service.load(players, 2025, threading.Event(), lambda m: None)
    assert len(calls) == 3 and second.requests == 0 and second.cache_hits == 2
    event = threading.Event(); event.set()
    with pytest.raises(Cancelled):
        service.load(players, 2025, event, lambda m: None)
    with pytest.raises(RaceError, match='batting'):
        service.load([players[0], RacePlayer(20, 'B', 'pit')], 2025, threading.Event(), lambda m: None)


def test_invalid_response_not_saved(tmp_path, monkeypatch):
    db = SQLiteManager(tmp_path/'ops.db'); service = OpsRaceService(db)
    monkeypatch.setattr(service, '_get', lambda url, *args: schedule() if url.endswith('schedule')
                        else payload([fixture_row(hits=None)]))
    with pytest.raises(RaceError):
        service.load([RacePlayer(10, 'A', 'bat')]*2, 2025, threading.Event(), lambda m: None)
    assert db.get_player_stats(10, SOURCE, 2025, 'bat:R', 30) is None


def test_mlb_cache_clear_includes_ops_only(tmp_path, monkeypatch):
    import services.settings_service as settings
    monkeypatch.setattr(settings, 'CACHE_DIR', tmp_path/'cache')
    db = SQLiteManager(tmp_path/'ops.db')
    db.set_player_stats(10, SOURCE, 2025, 'bat:R', {'x': 1})
    db.set_player_stats(10, 'fangraphs_race_v1', 2025, 'bat', {'x': 1})
    settings.clear_cache(db, 'MLB')
    assert db.get_player_stats(10, SOURCE, 2025, 'bat:R', 30) is None
    assert db.get_player_stats(10, 'fangraphs_race_v1', 2025, 'bat', 30)


def test_postponed_and_resumed_schedule_entries_are_not_counted_twice():
    data = schedule()
    old = copy.deepcopy(data['dates'][0]['games'][0])
    old['status']['detailedState'] = 'Postponed'
    data['dates'].append({'date': '2025-03-31', 'games': [old]})
    data['dates'].append(copy.deepcopy(data['dates'][0]))
    axis, games = completed_schedule(data, 2025, date(2025, 4, 4))
    assert games == {1: '2025-04-01', 2: '2025-04-02', 3: '2025-04-03'}
    assert cumulative_ops([fixture_row()], axis, games, 'now')[axis.end].pa == 5
