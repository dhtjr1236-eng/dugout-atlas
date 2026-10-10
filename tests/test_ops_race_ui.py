from __future__ import annotations

from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication

from config.i18n import set_language, tr
from services.fangraphs_service import FanGraphsService
from services.ops_race import OpsResult, cumulative_ops
from services.season_race import RacePlayer
from tests.test_ops_race import axis_games, fixture_row
from tests.test_season_race import MemoryDB
from ui.season_race_view import SeasonRaceView


@pytest.fixture
def view():
    app = QApplication.instance() or QApplication([])
    w = SeasonRaceView(SimpleNamespace(fangraphs=FanGraphsService(MemoryDB())))
    w.players = [RacePlayer(10, 'Player A', 'bat'), RacePlayer(20, 'Player B', 'bat')]
    w.metric.setCurrentIndex(1)
    w.resize(1200, 880)
    yield w, app
    w.close(); app.processEvents(); set_language('en')


def result():
    axis, games = axis_games()
    a = cumulative_ops([fixture_row(), fixture_row(2)], axis, games, '2025-10-01')
    b = cumulative_ops([fixture_row(hits=1, totalBases=1)], axis, games, '2025-10-01')
    return OpsResult(axis, (RacePlayer(10, 'Player A', 'bat'), RacePlayer(20, 'Player B', 'bat')), (a, b), 3, 0)


def test_ops_selection_routes_to_mlb_not_fangraphs(view, monkeypatch):
    w, app = view
    called = []
    monkeypatch.setattr(w.service, 'prepare', lambda *a: pytest.fail('OPS requested FanGraphs'))
    monkeypatch.setattr(w.ops_service, 'load', lambda players, season, *a: called.append((players, season)) or result())
    w.start('full')
    loop = QEventLoop(); QTimer.singleShot(250, loop.quit); loop.exec()
    assert len(called) == 1 and not w._workers
    assert w._confirmation is None
    assert w.figure.axes[0].get_ylabel() == 'OPS'
    assert '1.350' in w.summary_cards[0].text()
    assert '+0.700' in w.summary_cards[2].text()


def test_resample_changes_only_local_endpoints_and_keeps_fixed_axis(view, monkeypatch):
    w, _ = view
    w._ops_loaded(result())
    monkeypatch.setattr(w.ops_service, 'load', lambda *a: pytest.fail('filter requested network'))
    w.granularity.setCurrentIndex(3)
    assert len(w.axis.dates) == 3
    limits = w.figure.axes[0].get_ylim()
    w.slider.setValue(0)
    assert w.figure.axes[0].get_ylim() == limits
    assert '5 PA' in w.summary_cards[0].text()
    w.slider.setValue(2)
    assert '10 PA' in w.summary_cards[0].text()
    assert tr('Small sample: fewer than 50 PA.') in w.summary_cards[2].text()
    w.metric.setCurrentIndex(0)
    assert not w.points[0] and w._ops_result is None
    assert w.figure.axes[0].get_ylabel() == 'fWAR'


def test_pitching_ops_blocked_without_network(view, monkeypatch):
    w, _ = view
    w.role_boxes[1].setCurrentIndex(1)
    monkeypatch.setattr(w.ops_service, 'load', lambda *a: pytest.fail('pitching OPS requested'))
    w.start('full')
    assert w._last_error == 'OPS requires two batting roles.' and not w._workers


@pytest.mark.parametrize('language', ['en', 'ko', 'ja'])
def test_ops_localization_and_export(view, language, tmp_path):
    w, app = view
    set_language(language); w.retranslate(); w._ops_loaded(result())
    w.show(); app.processEvents()
    assert tr('OPS difference (A − B)') in w.summary_cards[2].text()
    assert 'FanGraphs' not in w.notice.text()
    assert w.save_image(tmp_path/f'ops-{language}.png')


def test_new_selection_clears_local_ops_result(view):
    from models.player import PlayerBundle, PlayerProfile
    w, _ = view
    w._ops_loaded(result())
    w.set_players([PlayerBundle(PlayerProfile(99, 'New')), PlayerBundle(PlayerProfile(100, 'Other'))], 2024)
    assert w._ops_result is None and w.points == [{}, {}]
