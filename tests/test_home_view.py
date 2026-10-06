from __future__ import annotations
import json
from datetime import date
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
import pytest
from ui.home_view import HomeView
from services.home_service import HomeSnapshot, load_home_snapshot
from database.sqlite_manager import SQLiteManager

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_empty_local_library_does_not_create_favorites(tmp_path):
    db = SQLiteManager(tmp_path / 'db.sqlite3')
    target = tmp_path / 'missing/favorites.json'
    snapshot = load_home_snapshot(db, 2025, target)
    assert snapshot.record_count == 0 and not snapshot.favorites
    assert not target.parent.exists()


def test_inventory_is_season_scoped_and_keeps_strict_ids(tmp_path):
    db = SQLiteManager(tmp_path / 'db.sqlite3')
    db.set_player_stats(1, 'test_source', 2025, 'bat', {'WAR': None})
    db.set_player_stats(2, 'test_source', 2024, 'bat', {'WAR': 99})
    path = tmp_path / 'favorites.json'
    path.write_text(json.dumps({'players': [{'id':1,'name':'A'}, {'id':1}, {'id':'2'}, {'id':True}]}))
    snapshot = load_home_snapshot(db, 2025, path)
    assert (snapshot.player_count,snapshot.source_count,snapshot.record_count)==(1,1,1)
    assert [row['id'] for row in snapshot.favorites]==[1]
    assert db.get_player_stats(1,'test_source',2025,'bat',1)['WAR'] is None


def test_bad_favorites_is_an_error(tmp_path):
    db = SQLiteManager(tmp_path / 'db.sqlite3')
    path=tmp_path/'favorites.json';path.write_text('{')
    with pytest.raises(ValueError): load_home_snapshot(db,2025,path)


def test_home_navigation_preserves_id_and_season(app):
    view=HomeView();view.season.setValue(2025)
    snapshot=HomeSnapshot(2025,({'id':660271,'name':'Shohei Ohtani','team':'LAD'},),1,1,1,'2025-10-01')
    view.set_snapshot(snapshot)
    selected=[];actions=[]
    view.player_selected.connect(lambda *args:selected.append(args))
    view.navigate_requested.connect(lambda *args:actions.append(args))
    view.favorites.itemClicked.emit(view.favorites.item(0))
    view.buttons['compare'].click()
    assert selected==[(660271,2025)] and actions==[('compare',2025)]
    assert view.favorites.item(0).data(Qt.ItemDataRole.UserRole)==660271
    view.set_state('error');assert view.favorites.item(0).data(Qt.ItemDataRole.UserRole)==660271
    view.set_snapshot(HomeSnapshot(2024,(),0,0,0,''));assert view._snapshot==snapshot
    view.close()


def test_home_loading_and_empty_are_distinct(app):
    view=HomeView();view.set_state('loading');assert not view.refresh.isEnabled()
    view.set_snapshot(HomeSnapshot(view.season.value(),(),0,0,0,''))
    assert view._state=='empty' and view.refresh.isEnabled()
    assert not view.favorites.item(0).flags() & Qt.ItemFlag.ItemIsEnabled
    view.set_schedule_state('empty','2025-12-01')
    assert view._schedule_state=='empty'
    view.set_schedule_state('error');assert view._schedule_state=='error'
    view.close()


def test_controller_discards_old_home_response(app,tmp_path,monkeypatch):
    from ui.main_window import MainWindow
    from controllers.app_controller import AppController
    window=MainWindow();controller=AppController(window,SQLiteManager(tmp_path/'db.sqlite3'))
    callbacks=[]
    monkeypatch.setattr(controller,'_run',lambda task,success,**kw:callbacks.append(success))
    controller.load_home()
    first_year=window.home_view.season.value()
    window.home_view.season.setValue(first_year-1)
    callbacks[0](HomeSnapshot(first_year,(),5,5,5,'old'))
    assert window.home_view._snapshot is None
    callbacks[-1](HomeSnapshot(first_year-1,(),2,2,2,'new'))
    assert window.home_view._snapshot.player_count==2
    window.close()


def test_main_home_actions_use_selected_season(app,tmp_path,monkeypatch):
    from ui.main_window import MainWindow
    from controllers.app_controller import AppController
    window=MainWindow();controller=AppController(window,SQLiteManager(tmp_path/'db.sqlite3'));window.controller=controller
    monkeypatch.setattr(controller,'load_home',lambda:None)
    calls=[];monkeypatch.setattr(controller,'load_league',lambda:calls.append(controller.season))
    window._navigate_home('standings',2024)
    assert calls==[2024] and window.tabs.currentWidget() is window.league_view
    window._navigate_home('compare',2023)
    assert window.tabs.currentWidget() is window.compare_view and controller.season==2023
    window.close()


def test_schedule_poll_does_not_reset_home_analysis_season(app,tmp_path,monkeypatch):
    from ui.main_window import MainWindow
    from controllers.app_controller import AppController
    window=MainWindow();controller=AppController(window,SQLiteManager(tmp_path/'db.sqlite3'))
    monkeypatch.setattr(controller,'_run',lambda task,success,**kw:success([]))
    controller.load_schedule('2026-12-01')
    controller.season=2024
    controller.load_schedule('2026-12-01')
    assert controller.season==2024
    controller.load_schedule('2025-12-01')
    assert controller.season==2025
    window.close()


@pytest.mark.parametrize('language',['en','ko','ja'])
def test_home_retranslation_and_narrow_layout(app,language):
    from config.i18n import set_language,tr
    set_language(language)
    view=HomeView();view.resize(500,820);view.show();app.processEvents()
    assert view._columns==1
    assert view.title.text()==tr('A home for every part of the season')
    assert view.horizontalScrollBar().maximum()==0
    view.close();set_language('en')


def test_large_font_narrow_home_scrolls_vertically(app):
    view=HomeView();view.setStyleSheet('QWidget { font-size: 17pt; }')
    view.resize(540,820);view.show();app.processEvents()
    assert view._columns==1
    assert view.horizontalScrollBar().maximum()==0
    assert view.verticalScrollBar().maximum()>0
    view.close()
