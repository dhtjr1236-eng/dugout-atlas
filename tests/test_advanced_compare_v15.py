from __future__ import annotations

import csv

from services.advanced_compare_service import percentile

def test_advanced_compare_percentile() -> None:
    assert percentile(3.0,[1.0,2.0,3.0,4.0]) == 75.0
    assert percentile(None,[1.0]) is None


def test_independent_seasons_and_race_guard(monkeypatch):
    from types import SimpleNamespace
    from PyQt6.QtWidgets import QApplication
    from models.player import PlayerBundle, PlayerProfile
    from ui.advanced_compare_window import AdvancedCompareWindow

    app = QApplication.instance() or QApplication([])
    window = AdvancedCompareWindow(SimpleNamespace(fangraphs=SimpleNamespace(db=SimpleNamespace())), 2026)
    pending = []
    monkeypatch.setattr(window, '_run', lambda task, success, on_error=None: pending.append((task, success)))
    monkeypatch.setattr(window.service, 'core_metrics', lambda bundle: {'OPS': bundle.basic.get('ops')})
    calls = []
    monkeypatch.setattr(window.service, 'statcast_percentiles', lambda bundle, season: calls.append((bundle.profile.id, season)) or {})
    try:
        window._load_slot(0, 1)
        window.slots[0].season.setValue(2025)
        window._load_slot(1, 2)
        assert not window.tabs.isTabEnabled(1)
        pending[0][1](PlayerBundle(PlayerProfile(1, 'old')))
        assert window.slots[0].bundle is None
        pending[1][1](PlayerBundle(PlayerProfile(1, 'Julio'), basic={'ops': .8}))
        pending[2][1](PlayerBundle(PlayerProfile(2, 'Lee'), basic={'ops': .9}))
        assert (1, 2025) in calls and (2, 2026) in calls
        assert '2025' in window.core_table.horizontalHeaderItem(1).text()
        assert '2026' in window.core_table.horizontalHeaderItem(2).text()
        window.slots[0].season.setValue(2026)
        assert window.tabs.isTabEnabled(1)
        assert window.slots[0].bundle is None
        pending[-1][1](PlayerBundle(PlayerProfile(1, 'Julio')))
        assert window.slots[0].bundle.profile.id == 1
    finally:
        window.close()
        app.processEvents()


def test_third_player_appears_in_race_and_mismatched_season_disables_tab(monkeypatch):
    from types import SimpleNamespace
    from PyQt6.QtWidgets import QApplication
    from models.player import PlayerBundle, PlayerProfile
    from ui.advanced_compare_window import AdvancedCompareWindow

    app = QApplication.instance() or QApplication([])
    window = AdvancedCompareWindow(SimpleNamespace(fangraphs=SimpleNamespace(db=SimpleNamespace())), 2025)
    pending = []
    monkeypatch.setattr(window, '_run', lambda task, success, on_error=None: pending.append(success))
    monkeypatch.setattr(window.service, 'core_metrics', lambda bundle: {'OPS': bundle.basic.get('ops')})
    monkeypatch.setattr(window.service, 'statcast_percentiles', lambda bundle, season: {})
    try:
        window._add_slot()
        for index in range(3):
            window._load_slot(index, index + 1)
            pending[-1](PlayerBundle(PlayerProfile(index + 1, f'Player {index + 1}'), basic={'ops': .8 + index / 10}))
        assert len(window.race.players) == 3
        assert window.tabs.isTabEnabled(1)
        assert window.core_table.columnCount() == 4
        window.slots[2].season.setValue(2024)
        assert not window.tabs.isTabEnabled(1)
        assert window.race.players == []
        pending[-1](PlayerBundle(PlayerProfile(3, 'Player 3')))
        assert not window.tabs.isTabEnabled(1)
        window.slots[2].season.setValue(2025)
        pending[-1](PlayerBundle(PlayerProfile(3, 'Player 3'), basic={'ops': 1.0}))
        assert window.tabs.isTabEnabled(1) and len(window.race.players) == 3
        window._add_slot()
        window.slots[3].season.setValue(2023)
        window._load_slot(3, 4)
        pending[-1](PlayerBundle(PlayerProfile(4, 'Player 4'), basic={'ops': .7}))
        assert window.tabs.isTabEnabled(1) and len(window.race.players) == 3
        assert window.core_table.columnCount() == 5
        window._load_slot(2, 5)
        stale = pending[-1]
        window.slots[2].clear_button.click()
        stale(PlayerBundle(PlayerProfile(5, 'Late response')))
        assert window.slots[2].bundle is None and window.slots[2].player_id is None
        assert len(window.race.players) == 2
        assert window.tabs.isTabEnabled(1)
    finally:
        window.close()
        app.processEvents()


def test_export_comparison_csv_uses_loaded_players_and_their_seasons(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from PyQt6.QtWidgets import QApplication, QFileDialog
    from models.player import PlayerBundle, PlayerProfile
    from ui.advanced_compare_window import AdvancedCompareWindow

    app = QApplication.instance() or QApplication([])
    window = AdvancedCompareWindow(SimpleNamespace(fangraphs=SimpleNamespace(db=SimpleNamespace())), 2025)
    window._add_slot()
    target = tmp_path / '비교.csv'
    monkeypatch.setattr(QFileDialog, 'exec', lambda _dialog: 1)
    monkeypatch.setattr(QFileDialog, 'selectedFiles', lambda _dialog: [str(target)])
    monkeypatch.setattr(window.service, 'statcast_percentiles',
                        lambda bundle, season: {'OPS': 88.6} if season == 2025 else {})
    try:
        assert not window.csv_button.isEnabled()
        window.slots[2].season.setValue(2024)
        window._loaded(0, PlayerBundle(PlayerProfile(1, '테스트, 선수'), basic={'ops': 0.91}))
        window._loaded(2, PlayerBundle(PlayerProfile(3, '=example')))
        assert window.csv_button.isEnabled()
        window.csv_button.click()
        for thread in list(window._threads):
            assert thread.wait(5000)
        app.processEvents()
        assert target.read_bytes().startswith(b'\xef\xbb\xbf')
        with target.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        ops = {(row['mlbam_id'], row['section']): row for row in rows if row['metric'] == 'OPS'}
        assert ops['1', 'basic']['player'] == '테스트, 선수'
        assert ops['1', 'basic']['value'] == '0.910'
        assert ops['3', 'basic']['player'] == "'=example"
        assert ops['3', 'basic']['season'] == '2024'
        assert ops['3', 'basic']['value'] == ''
        assert ops['1', 'statcast_percentile']['value'] == '89'
        assert ops['3', 'statcast_percentile']['value'] == ''

        monkeypatch.setattr(window.service, 'statcast_percentiles', lambda _bundle, _season: {})
        window._render()
        assert window.stat_table.rowCount() == 0
        window._clear_slot(0)
        assert not window.csv_button.isEnabled()
    finally:
        window.close()
        app.processEvents()
