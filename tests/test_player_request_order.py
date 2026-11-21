from types import SimpleNamespace
import pytest


@pytest.mark.parametrize('pitcher', [False, True])
def test_old_period_response_cannot_replace_new_season_and_retries_same_period(pitcher):
    from controllers.app_controller import AppController
    pending, shown, retried = [], [], []
    bundle = SimpleNamespace(profile=SimpleNamespace(id=1, full_name='A', is_pitcher=pitcher))
    view = SimpleNamespace(current_bundle=bundle, set_trend_loading=lambda p: None,
        set_pitcher_statcast_loading=lambda p: None, set_trend=lambda *a: shown.append(a),
        set_pitcher_statcast_period=lambda *a: shown.append(a))
    controller = SimpleNamespace(season=2025, selected_player_id=1, selected_player_season=None, _player_generation=1,
        _trend_busy=False, _pitcher_statcast_busy=False,
        window=SimpleNamespace(player_view=view, set_busy=lambda text: None),
        _run=lambda task, success, on_error: pending.append((success, on_error)),
        load_player_trend=lambda p: retried.append(p),
        load_pitcher_statcast_period=lambda p: retried.append(p),
        _default_error=lambda text: shown.append(text))
    loader = AppController.load_pitcher_statcast_period if pitcher else AppController.load_player_trend
    loader(controller, 'monthly')
    controller.season = 2026
    controller._player_generation += 1
    loader(controller, 'monthly')
    pending[0][0]({'label': '2025'} if pitcher else [{'season': 2025}])
    assert shown == []
    assert retried == ['monthly']


def test_installed_season_loader_discards_stale_results_and_allows_fast_changes(tmp_path, monkeypatch):
    # Production startup patches classes; isolate that installation from other tests.
    import os
    import subprocess
    import sys
    if os.environ.get('DUGOUT_REQUEST_ORDER_CHILD') != '1':
        result = subprocess.run([sys.executable, '-m', 'pytest',
            __file__ + '::test_installed_season_loader_discards_stale_results_and_allows_fast_changes', '-q'],
            env={**os.environ, 'DUGOUT_REQUEST_ORDER_CHILD': '1'}, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        return
    import asyncio
    from PyQt6.QtWidgets import QApplication
    from services import player_enhancements
    from controllers.app_controller import AppController
    from database.sqlite_manager import SQLiteManager
    from models.player import PlayerBundle, PlayerProfile
    from ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    player_enhancements.install_player_enhancements()
    window = MainWindow()
    controller = AppController(window, SQLiteManager(tmp_path / 'test.db'))
    pending, shown, errors = [], [], []
    monkeypatch.setattr(controller, '_run', lambda task, success, on_error=None: pending.append((task, success, on_error)))
    monkeypatch.setattr(controller, 'load_player_portrait', lambda pid: None)
    monkeypatch.setattr(controller, '_default_error', errors.append)
    monkeypatch.setattr(window, 'show_player', lambda bundle: shown.append(bundle.profile.id))
    try:
        controller.load_player(1, 2025)
        controller._select_player_season(2026)
        assert len(pending) == 2
        pending[0][2]('stale error')
        assert controller._player_busy and errors == []
        latest = PlayerBundle(PlayerProfile(1, 'Latest'))
        pending[1][1]((latest, [2026, 2025], 2026))
        pending[0][1]((PlayerBundle(PlayerProfile(1, 'Old')), [2025], 2025))
        assert shown == [1] and controller.selected_player_season == controller.season == 2026
        controller.load_player(2, 2025)
        controller.load_player(1, 2024)
        pending[-2][2]('old player failure')
        assert controller._player_busy and errors == []
        controller._player_seasons[1] = [2026, 2025]
        async def load(pid, season):
            return PlayerBundle(PlayerProfile(pid, str(season)))
        monkeypatch.setattr(controller.players, 'get_bundle', load)
        task, accept, _ = pending[-1]
        payload = asyncio.run(task())
        assert payload[2] == 2024  # Never silently substitute another year.
        accept(payload)
        assert controller.season == 2024 and not controller._player_busy
    finally:
        window.close()
        app.processEvents()
