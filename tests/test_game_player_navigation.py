from __future__ import annotations

from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtTest import QSignalSpy
from PyQt6.QtWidgets import QApplication, QDateEdit, QTabWidget, QWidget
from models.game import GameDetail, LineupPlayer, TeamRef
from ui.game_view import GameView
from ui.main_window import MainWindow


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_game_cells_emit_authoritative_id(app):
    view=GameView()
    player=LineupPlayer(660271,'Same Name','DH')
    detail=GameDetail(1,TeamRef(1,'Away'),TeamRef(2,'Home'),'Final',
                      batter=player,away_lineup=[player],raw={
        'gameData':{'game':{'season':'2024'},'datetime':{'officialDate':'2024-06-01'}},
        'liveData':{'plays':{'allPlays':[{'matchup':{
            'batter':{'id':660271,'fullName':'Same Name'},
            'pitcher':{'id':123,'fullName':'Same Name'}}}]}}})
    view.set_game(detail);spy=QSignalSpy(view.player_selected)
    assert view.boxscore.item(0,0).data(Qt.ItemDataRole.UserRole)==660271
    view.boxscore.itemClicked.emit(view.boxscore.item(0,0))
    view.plays.itemClicked.emit(view.plays.item(0,2))
    view.batter_button.click()
    view._select_item(view.linescore.item(0,0))
    assert [list(row) for row in spy]==[[660271],[123],[660271]]
    view.boxscore.cellEntered.emit(0,0)
    assert view.boxscore.viewport().cursor().shape()==Qt.CursorShape.PointingHandCursor
    view.close()


def test_main_navigation_uses_game_season(app):
    calls=[]
    tabs=QTabWidget(); player=QWidget(); tabs.addTab(QWidget(),'Game');tabs.addTab(player,'Player')
    window=SimpleNamespace(game_view=SimpleNamespace(game_season=2024,game_date='2024-06-01'),
                           date_edit=QDateEdit(QDate(2026,1,1)),tabs=tabs,player_view=player,
                           controller=SimpleNamespace(load_player=lambda *args:calls.append(args)))
    MainWindow._open_game_player(window,660271)
    assert calls==[(660271,2024)] and tabs.currentWidget() is player
    assert window.date_edit.date()==QDate(2024,6,1)


def test_scoring_runner_cells_keep_separate_ids(app):
    from services.live_scoring import install_live_scoring_support
    install_live_scoring_support()
    view=GameView()
    runners=[{'movement':{'end':'score'},'details':{'runner':{'id':pid,'fullName':'Same Name'}}}
             for pid in (10,20)]
    detail=GameDetail(1,TeamRef(1,'A'),TeamRef(2,'B'),'Final',raw={
        'liveData':{'plays':{'allPlays':[{'runners':runners,'about':{'isScoringPlay':True}}]}}})
    view.set_game(detail)
    spy=QSignalSpy(view.player_selected)
    for row in range(2):
        view.scoring_table.itemClicked.emit(view.scoring_table.item(row,1))
    assert [list(row) for row in spy]==[[10],[20]]
    view.close()


def test_controller_discards_same_player_stale_season(app):
    from controllers.app_controller import AppController
    callbacks=[];shown=[]
    controller=SimpleNamespace(season=2025,_player_busy=False,selected_player_id=None,
        window=SimpleNamespace(show_player_loading=lambda pid:None,
            show_player=lambda bundle:shown.append(bundle),set_busy=lambda text:None,
            player_view=SimpleNamespace(current_trend_period='yearly')),
        _run=lambda task,success,on_error:callbacks.append((success,on_error)))
    AppController.load_player(controller,1,2024)
    AppController.load_player(controller,1,2025)
    old=SimpleNamespace(profile=SimpleNamespace(full_name='Old',is_pitcher=False))
    new=SimpleNamespace(profile=SimpleNamespace(full_name='New',is_pitcher=False))
    callbacks[0][0](old)
    assert not shown and controller._player_busy
    callbacks[1][0](new)
    assert shown==[new] and not controller._player_busy
