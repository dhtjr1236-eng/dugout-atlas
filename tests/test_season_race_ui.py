from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

import pytest
from PyQt6.QtWidgets import QApplication
from config.i18n import set_language
from config.theme_tokens import set_active_theme, set_active_accent, chart_colors
from models.player import PlayerBundle, PlayerProfile
from services.fangraphs_service import FanGraphsService
from services.season_race import Point, RacePlayer, SeasonAxis, demo_points, point_from_row
from tests.test_season_race import MemoryDB, real_axis, FIXTURES
from ui.season_race_view import SeasonRaceView

@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])

@pytest.fixture
def view(app):
    w=SeasonRaceView(SimpleNamespace(fangraphs=FanGraphsService(MemoryDB())))
    w.players=[RacePlayer(1,'Player A','bat'),RacePlayer(2,'Player B','pit')]
    w.axis=real_axis();w.points=demo_points(w.axis);w._demo=True
    w.slider.setRange(0,len(w.axis.dates)-1);w.resize(1200,800)
    w.show();app.processEvents()
    yield w
    w.close();app.processEvents();set_language('en');set_active_theme('dark');set_active_accent('blue')


def test_live_original_war_equals_ui_values(view):
    view._demo=False
    view.players=[RacePlayer(592450,'Aaron Judge','bat',15640),RacePlayer(669373,'Tarik Skubal','pit',22267)]
    view.points=[{},{}]
    for i,role in enumerate(('bat','pit')):
        for end in ('2025-05-01','2025-06-01'):
            raw=json.loads((FIXTURES/f'{role}_{end}.json').read_text())['rows'][0]
            view.points[i][end]=point_from_row(raw,end,'2026-09-28')
    for end in ('2025-05-01','2025-06-01'):
        view.slider.setValue(view.axis.dates.index(end))
        for points in view.points: assert repr(points[end].war) in view.values.text()
    view.slider.setValue(view.axis.dates.index('2025-05-02'))
    assert view.values.text().count('No sampled point')==2


def test_play_pause_restart_speed_and_shared_end(view):
    view.toggle_play();assert view.timer.isActive()
    view.toggle_play();assert not view.timer.isActive()
    view.speed.setCurrentIndex(3);assert view.timer.interval()==175
    view.slider.setValue(view.slider.maximum()-1)
    view.toggle_play();view._advance()
    assert view.slider.value()==view.slider.maximum() and not view.timer.isActive()
    assert str(view.points[0][view.axis.dates[-1]].war) in view.values.text()
    assert str(view.points[1][view.axis.dates[-1]].war) in view.values.text()
    view.reset();assert view.slider.value()==0 and not view._seen


def test_peak_once_ties_and_effects_off(view):
    day=next(d for d,p in view.points[0].items() if p.war==1.8)
    idx=view.axis.dates.index(day)
    view.slider.setValue(idx);assert 0 in view._sparkles
    view.slider.setValue(idx+1);view.slider.setValue(idx);assert 0 not in view._sparkles
    view.reset();view.effects.setChecked(True);view.slider.setValue(idx)
    assert not view._sparkles and '1.8' in view.values.text()


def test_declining_marker_matches_line(view):
    day=view.axis.dates[-1];view.slider.setValue(view.slider.maximum())
    ax=view.figure.axes[0]
    from matplotlib.offsetbox import AnnotationBbox
    faces=[a for a in ax.artists if isinstance(a,AnnotationBbox)]
    assert [a.xy[1] for a in faces]==[.9,2.8]
    lines=[l for l in ax.lines if l.get_label() in ('Demo A','Demo B')]
    assert [l.get_ydata()[-1] for l in lines]==[.9,2.8]


@pytest.mark.parametrize('language,expected',[('en','Season Race'),('ko','시즌 레이스'),('ja','シーズンレース')])
def test_language_refresh(view,language,expected):
    set_language(language);view.retranslate()
    assert expected in view.heading.text()
    assert view.notice.text() and view.play.text()


@pytest.mark.parametrize('theme',['light','dark'])
@pytest.mark.parametrize('accent',['blue','gold','purple','magenta','emerald'])
def test_theme_tokens_applied(view,theme,accent):
    from matplotlib.colors import to_rgba
    set_active_theme(theme);set_active_accent(accent);view._draw()
    assert view.figure.get_facecolor()==to_rgba(chart_colors()['figure'])
    assert view.figure.axes[0].get_ylabel()=='fWAR'


def test_png_jpeg_stills(view,tmp_path):
    from PIL import Image
    for ext in ('png','jpg'):
        path=tmp_path/f'race.{ext}'
        assert view.save_image(path)
        with Image.open(path) as img:
            assert img.width>500 and img.height>300
            assert img.format==('PNG' if ext=='png' else 'JPEG')


def test_cancel_and_hide_stop_timers(view,app):
    import threading
    event=threading.Event();view._cancel=event
    view.toggle_play();view.hide();app.processEvents()
    assert event.is_set() and not view.timer.isActive() and not view.effect_timer.isActive()


def test_advanced_window_keeps_report_and_adds_tab(app):
    from ui.advanced_compare_window import AdvancedCompareWindow
    w=AdvancedCompareWindow(SimpleNamespace(fangraphs=FanGraphsService(MemoryDB())),2025)
    assert w.tabs.count()==2 and w.core_table is not None and w.stat_table is not None
    bundles=[PlayerBundle(PlayerProfile(i,f'P{i}'),fangraphs={'fWAR':i},bref={'bWAR':i+.1}) for i in (1,2)]
    for slot,bundle in zip(w.slots,bundles): slot.bundle=bundle
    w._sync_race();w._render()
    texts=[w.core_table.item(r,0).text() for r in range(w.core_table.rowCount())]
    assert 'fWAR' in texts and 'bWAR' in texts
    # A stale load from another season must not replace the selected player.
    w._loaded(0,PlayerBundle(PlayerProfile(99,'Stale')),999,2024)
    assert w.slots[0].bundle.profile.id==1
    w.close()


def test_demo_opens_separate_window_without_touching_live_points(view,monkeypatch,app):
    from services.season_race import RaceService
    monkeypatch.setattr(RaceService,'schedule',lambda *a:real_axis())
    original=view.points
    view._demo=False
    view.start_demo()
    demo=view._demo_window
    assert demo is not None and demo is not view and demo._demo_only
    from PyQt6.QtCore import QEventLoop,QTimer
    loop=QEventLoop();QTimer.singleShot(250,loop.quit);loop.exec()
    assert view.points is original and not view._demo
    assert demo._demo and demo.axis is not None
    assert 'Fictional values' in demo.notice.text()
    demo.close()


def test_cancel_discards_queued_worker_result(view,monkeypatch,app):
    import threading
    from PyQt6.QtCore import QEventLoop,QTimer
    entered=threading.Event();release=threading.Event();accepted=[]
    def task(cancel,emit):
        entered.set();release.wait(2)
        return 'old data'
    view._launch(task,accepted.append)
    assert entered.wait(1)
    view.cancel();release.set()
    loop=QEventLoop();QTimer.singleShot(150,loop.quit);loop.exec()
    assert not accepted and not view._workers
