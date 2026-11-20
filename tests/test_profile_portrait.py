import asyncio
from io import BytesIO
from PIL import Image
from PyQt6.QtWidgets import QApplication
from models.player import PlayerProfile


def png():
    data = BytesIO()
    Image.new('RGB', (240, 300), 'blue').save(data, format='PNG')
    return data.getvalue()


def test_profile_photo_rejects_stale_player_and_preserves_fallback():
    from ui.components.profile_portrait import ProfilePortrait
    app = QApplication.instance() or QApplication([])
    widget = ProfilePortrait()
    widget.set_profile(PlayerProfile(1, 'A'))
    widget.set_photo(2, png())
    assert widget.photo.isNull()
    widget.set_photo(1, png())
    assert not widget.photo.isNull()
    widget.set_profile(PlayerProfile(2, 'B'))
    assert widget.photo.isNull()
    widget.close()


def test_official_id_download_is_cached_separately(tmp_path, monkeypatch):
    from config import settings
    from services import headshots
    monkeypatch.setattr(settings, 'CACHE_DIR', tmp_path)
    calls = []
    async def fetch(url, **kwargs):
        calls.append(url)
        return png()
    monkeypatch.setattr(headshots, 'async_get_bytes', fetch)
    first = asyncio.run(headshots.load_profile_portrait(123))
    assert first and asyncio.run(headshots.load_profile_portrait(123)) == first
    assert len(calls) == 1 and '/people/123/' in calls[0] and 'w_320' in calls[0]
    assert not (tmp_path / 'headshots' / '123.png').exists()


def test_portrait_download_runs_with_installed_player_season_extension(tmp_path, monkeypatch):
    # The production installer patches classes process-wide. Exercise startup in
    # its own process so unrelated base-controller tests keep their own startup.
    import os
    import subprocess
    import sys
    if os.environ.get('DUGOUT_PHOTO_REGRESSION_CHILD') != '1':
        result = subprocess.run([sys.executable, '-m', 'pytest',
                                 __file__ + '::test_portrait_download_runs_with_installed_player_season_extension',
                                 '-q'], env={**os.environ, 'DUGOUT_PHOTO_REGRESSION_CHILD': '1'},
                                capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        return
    from services import player_enhancements, headshots
    from ui.main_window import MainWindow
    from controllers.app_controller import AppController
    from database.sqlite_manager import SQLiteManager
    from models.player import PlayerBundle
    app = QApplication.instance() or QApplication([])
    player_enhancements.install_player_enhancements()
    window = MainWindow()
    controller = AppController(window, SQLiteManager(tmp_path / 'test.sqlite3'))
    async def seasons(_player):
        return [2026]
    async def bundle(player, _season):
        return PlayerBundle(PlayerProfile(player, f'Player {player}'))
    downloads = []
    async def portrait(player):
        downloads.append(player)
        return png()
    monkeypatch.setattr(player_enhancements, '_available_player_seasons', seasons)
    monkeypatch.setattr(controller.players, 'get_bundle', bundle)
    monkeypatch.setattr(headshots, 'load_profile_portrait', portrait)
    monkeypatch.setattr(controller, '_run', lambda task, success, **kw: success(asyncio.run(task())))
    try:
        for player in (677594, 808982):
            controller.load_player(player, 2026)
            assert downloads[-1:] == [player]
            assert not window.player_view.portrait.photo.isNull()
    finally:
        window.close()
