from __future__ import annotations

import json

import pytest
from PyQt6.QtWidgets import QApplication

from config.i18n import set_language, tr
from database.sqlite_manager import SQLiteManager
from services.fangraphs_service import FG_CACHE_SOURCE
from services.home_service import load_home_snapshot
from ui.home_view import HomeView
from ui.season_recap import format_recap_value


def favorite_file(tmp_path, **extra):
    path = tmp_path / 'favorites.json'
    path.write_text(json.dumps({'players': [{'id': 1, 'name': 'Test <Player>', **extra}]}))
    return path


def test_recap_uses_annual_source_and_same_role_even_after_cache_expiry(tmp_path):
    db = SQLiteManager(tmp_path / 'test.sqlite3')
    db.set_player_stats(1, FG_CACHE_SOURCE, 2025, 'batter', {'OPS': '.900', 'HR': 0, 'fWAR': 4.2})
    db.set_player_stats(1, FG_CACHE_SOURCE, 2024, 'batter', {'OPS': '.800', 'HR': 10, 'fWAR': 3.0})
    db.set_player_stats(1, FG_CACHE_SOURCE, 2025, 'history_batter', {'OPS': 99})
    db.set_player_stats(1, 'unrelated_postseason', 2025, 'batter', {'OPS': 99})
    with db.connection() as connection:
        connection.execute("UPDATE player_stats SET updated_at='2000-01-01T00:00:00+00:00'")
    snapshot = load_home_snapshot(db, 2025, favorite_file(tmp_path))
    recap, = snapshot.recaps
    assert recap.role == 'batter'
    assert recap.metrics[0].delta == pytest.approx(.1)
    assert recap.metrics[1].current == 0
    assert recap.metrics[1].delta == -10
    assert recap.current_updated_at.startswith('2000-')
    assert load_home_snapshot(db, 2023, favorite_file(tmp_path)).recaps[0].metrics[0].current is None


def test_recap_missing_invalid_and_corrupt_values_stay_missing(tmp_path):
    db = SQLiteManager(tmp_path / 'test.sqlite3')
    db.set_player_stats(1, FG_CACHE_SOURCE, 2025, 'pitcher', {'ERA': 'nan', 'K%': True, 'fWAR': None})
    db.set_player_stats(1, FG_CACHE_SOURCE, 2024, 'pitcher', {'ERA': 2, 'K%': 20, 'fWAR': 3})
    recap, = load_home_snapshot(db, 2025, favorite_file(tmp_path, position='P')).recaps
    assert all(metric.current is None and metric.delta is None for metric in recap.metrics)
    with db.connection() as connection:
        connection.execute("UPDATE player_stats SET data_json='broken'")
    recap, = load_home_snapshot(db, 2025, favorite_file(tmp_path, position='P')).recaps
    assert recap.role == 'pitcher'
    assert all(metric.previous is None for metric in recap.metrics)


def test_two_way_players_have_separate_batting_and_pitching_recaps(tmp_path):
    db = SQLiteManager(tmp_path / 'test.sqlite3')
    db.set_player_stats(1, FG_CACHE_SOURCE, 2025, 'batter', {'fWAR': 4})
    db.set_player_stats(1, FG_CACHE_SOURCE, 2024, 'pitcher', {'fWAR': 3})
    batting, pitching = load_home_snapshot(db, 2025, favorite_file(tmp_path)).recaps
    assert batting.metrics[-1].delta is None
    assert pitching.metrics[-1].delta is None
    assert batting.metrics[-1].current == 4
    assert pitching.metrics[-1].previous == 3


@pytest.mark.parametrize('language', ['en', 'ko', 'ja'])
@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_recap_navigation_language_theme_and_narrow_layout(tmp_path, language, theme):
    from config.settings import THEME_QSS_PATH
    from config.theme_tokens import tokens_for

    app = QApplication.instance() or QApplication([])
    db = SQLiteManager(tmp_path / 'test.sqlite3')
    db.set_player_stats(1, FG_CACHE_SOURCE, 2025, 'batter', {'OPS': .9, 'HR': 20, 'fWAR': 4})
    snapshot = load_home_snapshot(db, 2025, favorite_file(tmp_path))
    view = HomeView()
    try:
        view.season.setValue(2025)
        stylesheet = THEME_QSS_PATH.read_text(encoding='utf-8')
        for name, value in tokens_for(theme).items():
            stylesheet = stylesheet.replace('{{' + name + '}}', value)
        view.setStyleSheet(stylesheet)
        view.setStyleSheet(view.styleSheet() + '\nQWidget { font-size: 24pt; }')
        view.set_snapshot(snapshot)
        set_language(language)
        view.retranslate()
        assert view.recap_heading.text() == tr('Season in review · favorite players')
        assert view.recap_cards[0].open_button.text() == tr('Open player analysis')
        selected = []
        view.player_selected.connect(lambda *args: selected.append(args))
        view.recap_cards[0].open_button.click()
        assert selected == [(1, 2025)]
        view.resize(540, 820)
        view.show()
        app.processEvents()
        assert view.horizontalScrollBar().maximum() == 0
        view.set_state('loading')
        assert not view.recap_cards[0].isEnabled()
        view.season.setValue(2024)
        assert not view.recap_cards
        view.set_snapshot(snapshot)
        assert view._snapshot is None
    finally:
        view.close()
        set_language('en')


def test_percentage_point_delta_and_missing_display():
    assert format_recap_value('K%', 3.5, signed=True) == '+3.5 pp'
    assert format_recap_value('OPS', None) == '—'
    assert format_recap_value('HR', 0) == '0'
