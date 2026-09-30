from __future__ import annotations

import threading
from datetime import date, timedelta

import pytest
from services.season_race import Point, RaceError, RacePlayer, SeasonAxis, sample_dates
from tests.test_season_race import service


def axis():
    start = date(2025, 4, 1)
    days = tuple((start + timedelta(days=i)).isoformat() for i in range(183))
    return SeasonAxis(2025, days[0], days[-1], days)


def test_monthly_last_real_day():
    assert sample_dates(axis(), 'monthly') == ('2025-04-30','2025-05-31','2025-06-30',
                                              '2025-07-31','2025-08-31','2025-09-30')


def test_biweekly_calendar_intervals_and_final():
    dates = sample_dates(axis(), 'bi-weekly')
    assert len(dates) == 14
    assert dates[0] == axis().start and dates[-1] == axis().end
    assert all((date.fromisoformat(b)-date.fromisoformat(a)).days == 14
               for a,b in zip(dates,dates[1:]))


def test_range_and_sparse_schedule():
    assert len(sample_dates(axis(), 'range', '2025-05-01', '2025-05-31')) == 31
    assert sample_dates(axis(), 'monthly', '2025-05-10', '2025-06-15') == ('2025-05-31','2025-06-15')
    sparse = SeasonAxis(2025, '2025-04-01', '2025-04-30', ('2025-04-01','2025-04-16','2025-04-29'))
    assert sample_dates(sparse, 'bi-weekly') == sparse.dates
    with pytest.raises(RaceError): sample_dates(axis(), 'full','2025-06-01','2025-05-01')


def test_local_preflight_and_snapshot_budget(service, monkeypatch):
    player = RacePlayer(1, 'A', 'bat', 2)
    cached = Point('2025-04-30', .2, 'now')
    monkeypatch.setattr(service, 'cached', lambda p,a,d: cached if d == cached.day else None)
    monkeypatch.setattr(service, '_request', lambda *args: pytest.fail('preflight used network'))
    service.interval = 1
    plan = service.plan([player], axis(), 'monthly')
    assert (plan.total_jobs, plan.cache_hits, plan.new_jobs, plan.estimated_seconds) == (6,1,5,5)
    calls=[]
    monkeypatch.setattr(service, 'fetch', lambda p,a,d,c: calls.append((a.start,d)))
    service.execute(plan, threading.Event(), lambda m: None)
    assert len(calls)==5 and all(start == '2025-04-01' for start, _ in calls)


def test_full_confirmation_is_nonblocking_and_reject_stops_requests(monkeypatch):
    from PyQt6.QtWidgets import QApplication, QMessageBox
    from types import SimpleNamespace
    from services.fangraphs_service import FanGraphsService
    from tests.test_season_race import MemoryDB
    from ui.season_race_view import SeasonRaceView
    app=QApplication.instance() or QApplication([])
    view=SeasonRaceView(SimpleNamespace(fangraphs=FanGraphsService(MemoryDB())))
    players=[RacePlayer(1,'A','bat',2), RacePlayer(3,'B','pit',4)]
    view.players=players
    plan=view.service.plan(players,axis(),'full')
    monkeypatch.setattr(view.service,'execute',lambda *args: pytest.fail('unapproved execution'))
    view._prepared(plan,'full')
    assert view._confirmation is not None
    assert str(plan.new_jobs) in view._confirmation.text()
    view._confirmation.done(QMessageBox.StandardButton.No)
    app.processEvents()
    assert view._confirmation is None and view.mode=='Cancelled'
    view.close()


def test_full_confirmation_accept_executes_frozen_plan(monkeypatch):
    from PyQt6.QtWidgets import QApplication, QMessageBox
    from types import SimpleNamespace
    from services.fangraphs_service import FanGraphsService
    from tests.test_season_race import MemoryDB
    from ui.season_race_view import SeasonRaceView
    app=QApplication.instance() or QApplication([])
    view=SeasonRaceView(SimpleNamespace(fangraphs=FanGraphsService(MemoryDB())))
    view.players=[RacePlayer(1,'A','bat',2),RacePlayer(3,'B','pit',4)]
    plan=view.service.plan(view.players,axis(),'full')
    launched=[]
    monkeypatch.setattr(view,'_launch',lambda task,done:launched.append(task))
    view._prepared(plan,'full')
    view._confirmation.done(QMessageBox.StandardButton.Yes)
    app.processEvents()
    assert len(launched)==1
    used=[]
    monkeypatch.setattr(view.service,'execute',lambda approved,*args:used.append(approved))
    launched[0](threading.Event(),lambda m:None)
    assert used==[plan]
    view.close()
