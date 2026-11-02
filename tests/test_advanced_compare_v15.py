from __future__ import annotations

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
