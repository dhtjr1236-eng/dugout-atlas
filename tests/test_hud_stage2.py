from types import SimpleNamespace
import pytest
from PyQt6.QtWidgets import QApplication
from config.i18n import set_language, tr
from models.player import PlayerBundle, PlayerProfile
from ui.components.comparison_visuals import PercentileRadar, VALUE_ROLE, RANGE_ROLE


def test_radar_only_uses_shared_finite_actual_percentiles():
    app = QApplication.instance() or QApplication([])
    radar = PercentileRadar()
    try:
        radar.set_data(['A', 'B'], [dict(xBA=70, xSLG=80, xwOBA=90, EV=None),
                                    dict(xBA=40, xSLG=50, xwOBA=60, EV=90)])
        assert radar.metrics == ['xBA', 'xSLG', 'xwOBA']
        assert radar.series[0]['xBA'] == 70
        radar.set_data(['A', 'B'], [dict(xBA=70, xSLG=float('nan')), dict(xBA=40, xSLG=110)])
        assert radar.metrics == ['xBA']
        assert not radar.grab().isNull()
    finally:
        radar.close()


def test_comparison_bars_keep_negative_missing_and_per_season_values(monkeypatch):
    from ui.advanced_compare_window import AdvancedCompareWindow
    app = QApplication.instance() or QApplication([])
    window = AdvancedCompareWindow(SimpleNamespace(fangraphs=SimpleNamespace(db=SimpleNamespace())), 2026)
    try:
        window.slots[0].season.setValue(2025)
        window.slots[0].bundle = PlayerBundle(PlayerProfile(1, 'A'), fangraphs={'fWAR': -1.5})
        window.slots[1].bundle = PlayerBundle(PlayerProfile(2, 'B'), fangraphs={'fWAR': 3., 'OPS': .8})
        monkeypatch.setattr(window.service, 'core_metrics', lambda p: {'fWAR': p.fangraphs['fWAR'], 'OPS': p.fangraphs.get('OPS')})
        monkeypatch.setattr(window.service, 'statcast_percentiles', lambda p, year: {'xBA': 75 if year == 2025 else 25})
        window._render()
        window._sync_race()
        assert window.core_table.item(0, 1).data(VALUE_ROLE) == -1.5
        assert window.core_table.item(0, 1).data(RANGE_ROLE) == [-1.5, 3.] or window.core_table.item(0, 1).data(RANGE_ROLE) == (-1.5, 3.)
        assert window.core_table.item(1, 1).text() == '—'
        assert window.core_table.item(1, 1).data(VALUE_ROLE) is None
        assert window.radar.series == [{'xBA': 75}, {'xBA': 25}]
        assert not window.tabs.isTabEnabled(1)
        for i in (2, 3):
            window._add_slot()
            window.slots[i].bundle = PlayerBundle(PlayerProfile(i+1, str(i)), fangraphs={'fWAR': 0})
        window._render()
        assert window.core_table.columnCount() == 5
    finally:
        window.close()


@pytest.mark.parametrize('language', ['en', 'ko', 'ja'])
def test_player_profile_keeps_installed_season_selector_and_reflows(language):
    from services.player_enhancements import install_player_enhancements
    from ui.player_view import PlayerView
    app = QApplication.instance() or QApplication([])
    install_player_enhancements()
    set_language(language)
    view = PlayerView()
    try:
        assert view.identity_layout.indexOf(view.player_name_row) >= 0
        assert view.profile_heading.text() == tr('01 / PLAYER PROFILE')
        assert view.layout.indexOf(view.analysis_panel) < view.layout.indexOf(view.advanced_box)
        view.resize(700, 900)
        view.show()
        app.processEvents()
        assert view._hero_stacked
        assert view.name_label.width() > 0
        assert view.summary_grid.count() == 4
        view.resize(1600, 900)
        app.processEvents()
        assert not view._hero_stacked
        for period in ('yearly', 'monthly', 'daily'):
            assert view.trend_period.findData(period) >= 0
    finally:
        view.close()
        set_language('en')
