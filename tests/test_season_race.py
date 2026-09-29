from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from services.fangraphs_service import FanGraphsService
from services.season_race import (
    Cancelled, Point, RaceError, RacePlayer, RaceService, SeasonAxis,
    demo_points, drawdown, peak, point_from_row, sample_dates, season_axis, strict_row,
)

FIXTURES = Path(__file__).parent / 'fixtures' / 'season_race'


def real_axis(year=2025):
    return season_axis(json.loads((FIXTURES/f'schedule_{year}.json').read_text()), year, date(2026,1,1))


class MemoryDB:
    def __init__(self): self.rows = {}
    def get_player_stats(self, pid, source, season, role, ttl): return self.rows.get((pid,source,season,role))
    def set_player_stats(self, pid, source, season, role, data): self.rows[pid,source,season,role] = data


@pytest.fixture
def service():
    return RaceService(FanGraphsService(MemoryDB()), interval=0)


@pytest.mark.parametrize('year,start,end', [(2024,'2024-03-20','2024-09-30'),(2025,'2025-03-18','2025-09-28')])
def test_real_schedule_bounds(year,start,end):
    axis=real_axis(year)
    assert (axis.start,axis.end)==(start,end)
    assert axis.dates[0]==start and axis.dates[-1]==end


def test_schedule_filters_and_literal_game_date():
    games = [
        {'gameType':'S','gameDate':'2025-02-01T20:00:00Z','status':{'abstractGameState':'Final'}},
        {'gameType':'R','gameDate':'2025-03-18T23:59:00Z','status':{'abstractGameState':'Final'}},
        {'gameType':'R','gameDate':'2025-03-19T00:01:00Z','status':{'abstractGameState':'Final'}},
        {'gameType':'R','gameDate':'2025-03-20T01:00:00Z','status':{'abstractGameState':'Live'}},
        {'gameType':'R','gameDate':'2025-03-21T01:00:00Z','status':{'abstractGameState':'Preview'}},
        {'gameType':'W','gameDate':'2025-10-01T20:00:00Z','status':{'abstractGameState':'Final'}},
    ]
    axis=season_axis({'dates':[{'date':'irrelevant','games':games}]},2025,date(2025,3,20))
    assert axis.dates==('2025-03-18','2025-03-19')
    assert axis.start=='2025-03-18' and axis.end=='2025-03-21'


def test_unfinished_game_does_not_form_complete_day():
    payload={'dates':[{'games':[
        {'gameType':'R','gameDate':'2025-05-01T12:00:00Z','status':{'abstractGameState':'Final'}},
        {'gameType':'R','gameDate':'2025-05-01T19:00:00Z','status':{'abstractGameState':'Live'}}]}]}
    assert not season_axis(payload,2025,date(2025,5,2)).dates


@pytest.mark.parametrize('role,pid,fid', [('bat',592450,15640),('pit',669373,22267)])
@pytest.mark.parametrize('end', ['2025-05-01','2025-06-01'])
def test_recorded_live_range_war_is_unmodified(service,monkeypatch,role,pid,fid,end):
    data=json.loads((FIXTURES/f'{role}_{end}.json').read_text())
    def request(url,params):
        assert params == data['params']
        return {'data':data['rows']}
    monkeypatch.setattr(service.fg,'_request_json',request)
    p=service.fetch(RacePlayer(pid,'Name is deliberately irrelevant',role,fid),real_axis(),end,threading.Event())
    assert p.war==data['rows'][0]['WAR']
    assert p.day==end


def test_id_rules_names_never_match_and_conflicts_fail():
    p=RacePlayer(1,'Same Name','bat')
    assert strict_row([{'Name':'Same Name','xMLBAMID':2,'playerid':3,'WAR':9}],p) is None
    assert strict_row([{'Name':'Same Name','playerid':3,'WAR':9}],p) is None
    p=RacePlayer(1,'Same Name','bat',3)
    with pytest.raises(RaceError,match='mismatch'): strict_row([{'xMLBAMID':2,'playerid':3}],p)
    with pytest.raises(RaceError,match='mismatch'): strict_row([{'xMLBAMID':1,'playerid':4}],p)


def test_traded_player_aggregate_only():
    p=RacePlayer(1,'Traded','bat',3)
    row={'xMLBAMID':1,'playerid':3,'Team':'2 Tms','WAR':1.23}
    assert strict_row([row],p)==row
    with pytest.raises(RaceError,match='splits'): strict_row([row,row],p)


def test_two_way_role_keys_are_separate(service):
    a=RacePlayer(1,'Two-way','bat',2);b=RacePlayer(1,'Two-way','pit',2)
    assert service.cache_role(a,real_axis(),'2025-05-01') != service.cache_role(b,real_axis(),'2025-05-01')
    with pytest.raises(RaceError): RacePlayer(1,'Unknown','both',2)


@pytest.mark.parametrize('war',[None,'',float('nan'),float('inf'),True,'invalid'])
def test_missing_or_invalid_war_never_becomes_zero(war):
    with pytest.raises(RaceError): point_from_row({'WAR':war},'2025-05-01','now')


def test_peak_tie_earliest_and_drawdown_threshold():
    points={str(i):Point(str(i),v,'now') for i,v in enumerate([0.0,1.8,1.8,1.4,1.3,0.9])}
    assert peak(points).day=='1'
    assert not drawdown(points,'0') and not drawdown(points,'3')
    assert drawdown(points,'4') and drawdown(points,'5')


def test_preview_is_subset_with_last_day():
    axis=real_axis()
    assert set(sample_dates(axis,True)) <= set(axis.dates)
    assert sample_dates(axis,True)[-1]==axis.dates[-1]
    assert sample_dates(axis,False)==axis.dates


def test_cache_and_inflight_dedupe(service,monkeypatch):
    calls=[]
    def request(url,params):
        calls.append(params)
        return {'data':[{'xMLBAMID':1,'playerid':2,'WAR':.25}]}
    monkeypatch.setattr(service.fg,'_request_json',request)
    p=RacePlayer(1,'P','bat',2);axis=real_axis();cancel=threading.Event()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:service.fetch(p,axis,'2025-05-01',cancel),range(2)))
    assert len(calls)==1 and results[0]==results[1]
    assert calls[0]['team']=='0' and calls[0]['ind']=='0'
    assert service.cached(p,axis,'2025-06-01') is None


def test_cancel_before_network(service,monkeypatch):
    monkeypatch.setattr(service.fg,'_request_json',lambda *a:pytest.fail('network called'))
    cancel=threading.Event();cancel.set()
    with pytest.raises(Cancelled):service.fetch(RacePlayer(1,'P','bat',2),real_axis(),'2025-05-01',cancel)


def test_missing_row_stays_missing(service,monkeypatch):
    monkeypatch.setattr(service.fg,'_request_json',lambda *a:{'data':[]})
    assert service.fetch(RacePlayer(1,'P','bat',2),real_axis(),'2025-05-01',threading.Event()) is None
    assert not service.db.rows


@pytest.mark.parametrize('status',[403,429])
def test_access_error_breaks_circuit(service,monkeypatch,status):
    import services.season_race as module
    monkeypatch.setattr(module,'_BLOCKED_UNTIL',0)
    calls=[]
    def request(*a):
        calls.append(1);raise RuntimeError(f'HTTP {status}')
    monkeypatch.setattr(service.fg,'_request_json',request)
    p=RacePlayer(1,'P','bat',2);axis=real_axis();c=threading.Event()
    with pytest.raises(RuntimeError):service.fetch(p,axis,'2025-05-01',c)
    with pytest.raises(RaceError,match='cooldown'):service.fetch(p,axis,'2025-06-01',c)
    assert len(calls)==1 and not service.db.rows


def test_transport_timeout_has_bounded_retries(monkeypatch):
    import requests
    import services.fangraphs_service as fg
    calls=[]
    def timeout(*a,**k):calls.append(1);raise requests.Timeout('timeout')
    monkeypatch.setattr(fg.requests,'get',timeout);monkeypatch.setattr(fg.time,'sleep',lambda _:None)
    with pytest.raises(Exception,match='timeout'):fg.FanGraphsService._request_json('url',{})
    assert len(calls)==fg.SETTINGS.request_retries


def test_preview_then_full_requests_only_missing(service,monkeypatch):
    axis=SeasonAxis(2025,'2025-03-18','2025-03-26',tuple(f'2025-03-{d}' for d in range(18,27)))
    monkeypatch.setattr(service,'schedule',lambda *a:axis)
    monkeypatch.setattr(service,'resolve',lambda p,*a:RacePlayer(p.mlbam_id,p.name,p.role,p.mlbam_id+10))
    calls=[]
    def request(url,params):
        calls.append(params)
        return {'data':[{'xMLBAMID':i,'playerid':i+10,'WAR':i/10} for i in (1,2)]}
    monkeypatch.setattr(service.fg,'_request_json',request)
    players=[RacePlayer(1,'A','bat'),RacePlayer(2,'B','pit')]
    messages=[]
    service.load(players,2025,True,threading.Event(),messages.append)
    preview_calls=len(calls)
    service.load(players,2025,False,threading.Event(),messages.append)
    plans=[m for m in messages if m['kind']=='plan']
    assert plans[1]['hits']==preview_calls
    assert len(calls)==len(axis.dates)*2
    assert all(c['startdate']==axis.start for c in calls)


def test_fictional_fixture_not_real_players_or_cache():
    a,b=demo_points(real_axis())
    assert peak(a).war==1.8 and peak(a).day[5:7]=='06'
    assert a[real_axis().dates[-1]].war==.9
    assert peak(b).war==3.1 and peak(b).day[5:7]=='09'
    assert {p.fetched_at for p in a.values()}=={'DEMO'}
