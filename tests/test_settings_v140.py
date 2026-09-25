from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from config import preferences
from config.i18n import set_language, tr, translate_widgets
from database.sqlite_manager import SQLiteManager
from services import settings_service


@pytest.fixture
def isolated_preferences(tmp_path, monkeypatch):
    local = QSettings(str(tmp_path / 'settings.ini'), QSettings.Format.IniFormat)
    monkeypatch.setattr(preferences, 'store', lambda: local)
    yield local
    set_language('en')


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_preferences_persist_and_validate(isolated_preferences):
    preferences.save_preferences({'language': 'ja', 'refresh_seconds': 90, 'font_scale': 140, 'notifications': False})
    assert preferences.read_preferences()['language'] == 'ja'
    assert preferences.read_preferences()['refresh_seconds'] == 90
    assert preferences.read_preferences()['notifications'] is False
    isolated_preferences.setValue('preferences/refresh_seconds', -200)
    isolated_preferences.setValue('preferences/language', 'invalid')
    assert preferences.read_preferences()['refresh_seconds'] == 15
    assert preferences.read_preferences()['language'] == 'ko'


def test_live_translation_and_metric_identity(app):
    root = QWidget()
    layout = QVBoxLayout(root)
    label = QLabel('타율: 안타 ÷ 타수')
    layout.addWidget(label)
    for language, expected in [('en', 'Batting average: hits / at-bats'), ('ja', '打率: 安打 ÷ 打数'), ('ko', '타율: 안타 ÷ 타수')]:
        set_language(language)
        translate_widgets(root)
        assert label.text() == expected
        assert tr('wRC+') == 'wRC+'
        assert tr('Aaron Judge') == 'Aaron Judge'
    set_language('en')
    assert tr('우세: Aaron Judge') == 'Advantage: Aaron Judge'
    root.close()


def test_source_cache_clear_preserves_other_sources_and_imports(tmp_path, monkeypatch):
    db = SQLiteManager(tmp_path / 'test.sqlite3')
    for source in ('fangraphs_v6', 'baseball_reference_v8', 'statcast_batter_v5'):
        db.set_player_stats(1, source, 2026, 'batter', {'WAR': 2})
    cache = tmp_path / 'cache'
    cache.mkdir()
    (cache / '__init__.py').write_text('# source')
    data = tmp_path / 'data'
    data.mkdir()
    (data / 'favorites.json').write_text('{}')
    (data / 'war_daily_bat.csv').write_text('WAR\n2')
    monkeypatch.setattr(settings_service, 'CACHE_DIR', cache)
    assert settings_service.clear_cache(db, 'FanGraphs') == 1
    assert db.get_player_stats(1, 'fangraphs_v6', 2026, 'batter', 1) is None
    assert db.get_player_stats(1, 'baseball_reference_v8', 2026, 'batter', 1)
    assert settings_service.clear_cache(db, 'Baseball-Reference') == 1
    settings_service.clear_cache(db)
    assert (cache / '__init__.py').exists()
    assert (data / 'favorites.json').exists()
    assert (data / 'war_daily_bat.csv').exists()


def test_data_location_copies_sqlite_and_keeps_original(tmp_path, monkeypatch):
    root = tmp_path / 'old'
    data = root / 'data'
    data.mkdir(parents=True)
    db = SQLiteManager(data / 'mlb_advanced_gameday.sqlite3')
    db.set_player_stats(7, 'baseball_reference_v8', 2026, 'batter', {'bWAR': 3.5})
    (data / 'favorites.json').write_text('{"players": []}')
    monkeypatch.setattr(settings_service, 'RUNTIME_ROOT', root)
    monkeypatch.setattr(settings_service, 'DATA_DIR', data)
    destination = tmp_path / 'new'
    settings_service.copy_data_location(str(destination), db)
    copied = SQLiteManager(destination / 'data' / db.db_path.name)
    assert copied.get_player_stats(7, 'baseball_reference_v8', 2026, 'batter', 1)['bWAR'] == 3.5
    assert (data / 'favorites.json').exists()
    assert (destination / 'data' / 'favorites.json').exists()
    with pytest.raises(ValueError):
        settings_service.copy_data_location(str(destination), db)
    with pytest.raises(ValueError):
        settings_service.copy_data_location(str(root / 'nested'), db)


def test_diagnostics_excludes_private_paths(tmp_path):
    db = SQLiteManager(tmp_path / 'private.sqlite3')
    report = settings_service.diagnostics(db, {'data_root': str(tmp_path), 'language': 'en'})
    assert str(tmp_path) not in json.dumps(report)
    assert 'data_root' not in report['settings']


def test_settings_save_applies_theme_and_intervals(app, isolated_preferences, tmp_path):
    from config.settings import THEME_QSS_PATH
    from controllers.app_controller import AppController
    from ui.main_window import MainWindow
    from ui.settings_dialog import SettingsDialog
    from ui.theme_manager import ThemeManager
    window = MainWindow()
    window.theme_manager = ThemeManager(app, THEME_QSS_PATH.read_text())
    window.theme_manager.settings = isolated_preferences
    controller = AppController(window, SQLiteManager(tmp_path / 'db.sqlite3'))
    dialog = SettingsDialog(window, controller)
    controller._threads.add(object())
    dialog._update_busy()
    assert not dialog.clear.isEnabled()
    assert not dialog.save_button.isEnabled()
    controller._threads.clear()
    dialog._update_busy()
    assert dialog.clear.isEnabled()
    dialog.refresh.setValue(75)
    dialog.player_refresh.setValue(600)
    dialog.font.setValue(130)
    dialog.language.setCurrentIndex(dialog.language.findData('ja'))
    dialog.notifications.setChecked(False)
    dialog._save()
    controller.apply_preferences()
    assert controller.refresh_timer.interval() == 75_000
    assert controller.player_refresh_timer.interval() == 600_000
    assert window.settings_button.text() == '設定'
    assert window.theme_manager.font_scale == 130
    assert preferences.read_preferences()['notifications'] is False
    controller.refresh_timer.stop()
    controller.player_refresh_timer.stop()
    dialog.guard.stop()
    dialog.close()
    window.close()


def test_all_existing_metric_explanations_have_english_and_japanese():
    from services.convenience_features import METRIC_TOOLTIPS
    for language in ('en', 'ja'):
        set_language(language)
        for explanation in METRIC_TOOLTIPS.values():
            if any('\uac00' <= c <= '\ud7a3' for c in explanation):
                assert not any('\uac00' <= c <= '\ud7a3' for c in tr(explanation)), explanation
    set_language('en')


def test_invalid_source_cannot_clear_cache(tmp_path):
    db = SQLiteManager(tmp_path / 'test.sqlite3')
    db.set_player_stats(1, 'fangraphs_v6', 2026, 'batter', {'WAR': 1})
    with pytest.raises(ValueError):
        settings_service.clear_cache(db, '../../data')
    assert db.get_player_stats(1, 'fangraphs_v6', 2026, 'batter', 1)
