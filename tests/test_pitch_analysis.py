"""Offline regressions; real-response fixture provenance is documented separately."""
from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace
import pandas as pd
import pytest
from services.pitch_analysis import analyze_pitches


def actual():
    return pd.read_csv(Path(__file__).parent / 'fixtures/pitch_analysis/savant_669373_2025-09-06.csv')


def test_actual_response_contract_and_distribution():
    frame=actual(); result=analyze_pitches(frame,669373,2025)
    assert result['total']==90
    assert result['quality']['release_speed']['valid']==90
    row=next(r for r in result['profile'] if r['pitch']=='FF' and r['field']=='release_speed')
    values=frame.loc[frame.pitch_type.eq('FF'),'release_speed']
    assert row['median']==pytest.approx(values.median())
    assert row['iqr']==pytest.approx(values.quantile(.75)-values.quantile(.25))
    assert sum(r['pitches'] for r in result['matchup']['hand']['rows'])==90


def test_missing_is_not_zero_and_low_samples_warn():
    frame=actual().iloc[:3].copy();frame['release_speed']=[None,98,99]
    result=analyze_pitches(frame,669373,2025)
    assert result['quality']['release_speed']['valid']==2
    assert result['status']=='partial'
    assert all(r['small'] for r in result['profile'])


def test_missing_fields_unverified_and_empty_season():
    result=analyze_pitches(actual().drop(columns=['release_spin_rate','stand']),669373,2025)
    assert result['quality']['release_spin_rate']['status']=='unverified'
    assert result['matchup']['hand']['status']=='unverified'
    assert result['status']=='partial'
    assert analyze_pitches(actual(),669373,2024)['status']=='empty'
    assert analyze_pitches(actual().drop(columns=['game_type']),669373,2025)['status']=='unverified'


def test_identity_is_authoritative():
    with pytest.raises(ValueError):analyze_pitches(actual(),123,2025)


def test_matchup_denominators_and_zero_swings():
    frame=actual().iloc[:4].copy();frame['stand']=['L','L','R',None]
    frame['description']='called_strike'
    result=analyze_pitches(frame,669373,2025)
    hand=result['matchup']['hand']
    assert hand['valid']==3 and hand['total']==4
    assert all(r['whiff'] is None and r['swings']==0 for r in hand['rows'])
    assert sum(r['usage'] for r in hand['rows'] if r['condition']=='L')==pytest.approx(100)


def test_shared_frame_reuses_one_download_and_returns_copies(tmp_path,monkeypatch):
    from database.sqlite_manager import SQLiteManager
    from services.statcast_service import StatcastService
    service=StatcastService(SQLiteManager(tmp_path/'db.sqlite3'))
    calls=[]
    def fetch(*args):calls.append(args);return actual()
    monkeypatch.setattr(service,'_pybaseball',lambda:SimpleNamespace(statcast_pitcher=fetch))
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        frames=list(pool.map(lambda _: service.pitcher_frame(669373,2025),range(2)))
    first=frames[0];first['release_speed']=0
    assert service.pitcher_frame(669373,2025).release_speed.gt(0).all()
    service.get_pitch_arsenal(669373,2025);service.get_velocity_history(669373,2025)
    assert len(calls)==1


def test_player_ui_keeps_arsenal_and_hides_analysis_for_hitter():
    from PyQt6.QtWidgets import QApplication
    from models.player import PlayerProfile, PlayerBundle
    from ui.player_view import PlayerView
    app=QApplication.instance() or QApplication([]);view=PlayerView()
    view.set_bundle(PlayerBundle(PlayerProfile(669373,'Pitcher',position='P')))
    assert not view.pitch_analysis_box.isHidden() and not view.pitch_box.isHidden()
    view.pitch_analysis.set_result(analyze_pitches(actual(),669373,2025))
    assert view.pitch_analysis.profile.rowCount()>0
    assert view.pitch_analysis.matchup.rowCount()>0
    view.set_bundle(PlayerBundle(PlayerProfile(1,'Hitter',position='CF')))
    assert view.pitch_analysis_box.isHidden() and view.pitch_box.isHidden()
    view.close();app.processEvents()


@pytest.mark.parametrize('change',['season','player'])
def test_controller_drops_late_analysis(change):
    from PyQt6.QtCore import QObject
    from controllers.app_controller import AppController
    from models.player import PlayerProfile, PlayerBundle
    controller=AppController.__new__(AppController);QObject.__init__(controller)
    rendered=[];jobs=[]
    analysis=SimpleNamespace(loading=lambda:None,set_result=rendered.append,failed=lambda:None)
    controller.window=SimpleNamespace(player_view=SimpleNamespace(current_bundle=PlayerBundle(PlayerProfile(669373,'P',position='P')),pitch_analysis=analysis))
    controller.players=SimpleNamespace(get_pitch_analysis=lambda *_: {})
    controller.selected_player_id=669373;controller.season=2025
    controller._run=lambda task,success,**kwargs:jobs.append(success)
    controller.load_pitch_analysis()
    if change=='season':controller.season=2024
    else:controller.selected_player_id=1
    jobs[0]({'status':'ready'})
    assert not rendered

# Dugout Atlas
# Copyright (c) 2026 dhtjr1236-eng
# Unauthorized redistribution or rebranding is prohibited.
