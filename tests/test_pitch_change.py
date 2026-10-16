"""Offline Change boundaries, sample accounting, cache opt-in and stale-result tests."""
from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace
import pandas as pd
import pytest
from services.pitch_change import analyze_change


def frame():
    # Synthetic dates/values test arithmetic only; field evidence is the real fixture.
    return pd.DataFrame(dict(pitcher=[669373]*5, pitch_type=['FF']*4+['SL'],
        game_type=['R']*5, game_date=['2025-06-30','2025-07-01','2025-07-01','2025-07-08','2025-07-01'],
        release_speed=[90,94,96,None,80], release_spin_rate=[2000,2100,2200,2300,2500]))


def test_cutoff_day_after_and_daily_same_pitch():
    p=analyze_change(frame(),669373,2025,'2025-07-01')
    r=p['pitches'][0];v=r['metrics']['release_speed']
    assert (r['pitch'],r['before_n'],r['after_n'])==('FF',1,3)
    assert v['before']['median']==90 and v['after']['median']==95
    assert v['delta_median']==5 and v['after']['iqr']==1
    assert v['after']['n']==2 and v['after']['missing']==1
    assert [x['date'] for x in v['points']]==['2025-06-30','2025-07-01','2025-07-08']
    assert v['points'][-1]['median'] is None
    assert p['movement']=={'IVB':'unverified','HB':'unverified'} and p['status']=='partial'


def test_weekly_pools_pitches_not_daily_medians():
    v=analyze_change(frame(),669373,2025,'2025-07-01','weekly')['pitches'][0]['metrics']['release_speed']
    assert v['points'][0]['date']=='2025-06-30'
    assert v['points'][0]['median']==94 and v['points'][0]['n']==3
    assert v['before']['n']==1 and v['after']['n']==2


def test_missing_invalid_and_low_samples():
    f=frame();f['release_speed']=[None,'bad',-1,float('inf'),80]
    r=analyze_change(f,669373,2025,'2025-07-01')['pitches'][0]['metrics']['release_speed']
    assert r['before']['missing']==1 and r['before']['excluded']==0
    assert r['after']['missing']==0 and r['after']['excluded']==3
    assert r['after']['n']==0 and r['after']['small']
    assert r['delta_median'] is None


@pytest.mark.parametrize('missing',['release_speed','release_spin_rate'])
def test_missing_metric_is_unavailable(missing):
    p=analyze_change(frame().drop(columns=missing),669373,2025,'2025-07-01')
    v=p['pitches'][0]['metrics'][missing]['after']
    assert v['status']=='unavailable' and v['missing']==v['total'] and v['n']==0


@pytest.mark.parametrize('missing',['game_date','game_type','pitch_type'])
def test_missing_required_columns(missing):
    assert analyze_change(frame().drop(columns=missing),669373,2025,'2025-07-01')['status']=='unavailable'


def test_empty_unknown_and_excluded_rows():
    assert analyze_change(frame().drop(columns=['release_speed','release_spin_rate']),669373,2025,'2025-07-01')['status']=='unavailable'
    assert analyze_change(pd.DataFrame(),669373,2025,'2025-07-01')['status']=='empty'
    f=frame();f['pitch_type']=None
    p=analyze_change(f,669373,2025,'2025-07-01')
    assert p['unclassified']==5 and p['pitches']==[]
    f=frame();f.loc[0,'game_date']='bad';f.loc[1,'game_type']='S';f.loc[2,'game_date']='2024-07-01'
    p=analyze_change(f,669373,2025,'2025-07-01')
    assert p['excluded_rows']==3 and p['total']==2
    with pytest.raises(ValueError):analyze_change(frame(),1,2025,'2025-07-01')
    with pytest.raises(ValueError):analyze_change(frame(),669373,2025,'2024-07-01')


def test_real_fixture_contract():
    f=pd.read_csv(Path(__file__).parent/'fixtures/pitch_analysis/savant_669373_2025-09-06.csv')
    p=analyze_change(f,669373,2025,'2025-09-06')
    assert p['total']==90 and sum(r['after_n'] for r in p['pitches'])==90
    assert all(r['before_n']==0 for r in p['pitches'])
    for field in ('release_speed','release_spin_rate'):
        assert sum(r['metrics'][field]['after']['n'] for r in p['pitches'])==90


def test_no_implicit_download_and_shared_cache(tmp_path,monkeypatch):
    from database.sqlite_manager import SQLiteManager
    from services.statcast_service import StatcastService
    from services.player_service import PlayerService
    stat=StatcastService(SQLiteManager(tmp_path/'db.sqlite3')); calls=[]
    def fetch(*args):calls.append(args);return frame()
    monkeypatch.setattr(stat,'_pybaseball',lambda:SimpleNamespace(statcast_pitcher=fetch))
    service=PlayerService.__new__(PlayerService);service.statcast=stat
    assert service.get_pitch_change(669373,2025,'2025-07-01','daily')['status']=='cache_miss'
    assert calls==[]
    service.get_pitch_change(669373,2025,'2025-07-01','daily',True)
    service.get_pitch_change(669373,2025,'2025-07-02','weekly')
    service.get_pitch_analysis(669373,2025)
    assert len(calls)==1
    # Expired raw cache must also require explicit permission, preserving existing TTL.
    k=next(iter(stat._pitch_frames));stat._pitch_frames[k]=(float('-inf'),frame())
    assert service.get_pitch_change(669373,2025,'2025-07-01','daily')['status']=='cache_miss'
    assert len(calls)==1


@pytest.mark.parametrize('change',['player','season','cutoff','view_season','revision','request','generation','none'])
def test_stale_responses(change):
    from PyQt6.QtCore import QObject
    from controllers.app_controller import AppController
    from models.player import PlayerProfile,PlayerBundle
    c=AppController.__new__(AppController);QObject.__init__(c)
    key=[2025,'2025-07-01','daily',0];renders=[];failures=[];jobs=[]
    v=SimpleNamespace(key=lambda:tuple(key),download=SimpleNamespace(isChecked=lambda:False),loading=lambda:None,set_result=renders.append,failed=lambda:failures.append(1))
    c.window=SimpleNamespace(player_view=SimpleNamespace(current_bundle=PlayerBundle(PlayerProfile(669373,'P',position='P')),pitch_analysis=SimpleNamespace(change=v)))
    c.selected_player_id=669373;c.season=2025;c.players=SimpleNamespace()
    c._run=lambda task,success,**kw:jobs.append((success,kw['on_error']))
    c.load_pitch_change()
    if change=='player':c.selected_player_id=1
    elif change=='season':c.season=2024
    elif change=='cutoff':key[1]='2025-07-02'
    elif change=='view_season':key[0]=2024
    elif change=='revision':key[3]=1
    elif change=='request':c._change_request+=1
    elif change=='generation':c._player_generation=1
    jobs[0][0]({});jobs[0][1]('failed')
    assert bool(renders)==(change=='none') and bool(failures)==(change=='none')


@pytest.mark.parametrize('language',['en','ko','ja'])
def test_ui_buttons_samples_and_translation(language):
    from PyQt6.QtWidgets import QApplication
    from config.i18n import set_language,translate_widgets
    from ui.pitch_analysis_view import PitchAnalysisView
    app=QApplication.instance() or QApplication([])
    set_language(language)
    view=PitchAnalysisView();v=view.change;v.reset(2025)
    v.cutoff.setDate(__import__('PyQt6.QtCore',fromlist=['QDate']).QDate(2025,7,1))
    emitted=[];v.requested.connect(lambda:emitted.append(1));v.load.click()
    assert emitted==[1] and not v.download.isChecked()
    v.set_result(analyze_change(frame(),669373,2025,'2025-07-01'))
    assert v.table.rowCount()==8 and v.samples.rowCount()==6
    assert len(v.figure.axes)==2 and len(v.figure.axes[0].lines)==2
    assert '30' in v.help.text() and 'IVB' in v.help.text()
    assert view.tabs.count()==3
    translate_widgets(view)
    assert v.table.item(0,4).text()=='1'
    old=v.key();v.cutoff.setDate(v.cutoff.date().addDays(1))
    assert v.key()!=old and not v.payload
    view.close();app.processEvents();set_language('en')

# Dugout Atlas
# Copyright (c) 2026 dhtjr1236-eng
# Unauthorized redistribution or rebranding is prohibited.
