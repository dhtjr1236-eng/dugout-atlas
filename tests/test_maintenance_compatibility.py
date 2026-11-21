from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
import sys

from config import preferences, paths


def test_source_retains_custom_data_root(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, 'frozen', raising=False)
    monkeypatch.setattr(preferences, 'read_preferences', lambda: {'data_root': str(tmp_path)})
    spec = importlib.util.spec_from_file_location('isolated_settings', paths.resource_path('config', 'settings.py'))
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    assert module.RUNTIME_ROOT == tmp_path
    assert module.DB_PATH == tmp_path / 'data/mlb_advanced_gameday.sqlite3'
    assert not module.DATA_DIR.exists()


def test_source_default_remains_legacy(monkeypatch):
    monkeypatch.delattr(sys, 'frozen', raising=False)
    monkeypatch.setattr(preferences, 'read_preferences', lambda: {'data_root': ''})
    spec = importlib.util.spec_from_file_location('isolated_settings', paths.resource_path('config', 'settings.py'))
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    assert module.RUNTIME_ROOT == paths.bundle_dir()
    assert module.DATA_DIR == paths.bundle_dir() / 'data'


def test_file_log_added_with_existing_handler_and_no_duplicates(tmp_path, monkeypatch):
    from config import logging_config
    root = logging.Logger('isolated-root')
    existing = logging.NullHandler()
    root.addHandler(existing)
    from types import SimpleNamespace
    isolated_logging = SimpleNamespace(**vars(logging))
    isolated_logging.getLogger = lambda: root
    monkeypatch.setattr(logging_config, 'logging', isolated_logging)
    monkeypatch.setattr(logging_config, 'LOG_DIR', tmp_path / 'logs')
    try:
        logging_config.configure_logging()
        logging_config.configure_logging()
        assert existing in root.handlers
        assert sum(getattr(h, '_dugout_role', None) == 'file' for h in root.handlers) == 1
        assert sum(getattr(h, '_dugout_role', None) == 'console' for h in root.handlers) == 1
        root.warning('한글 로그')
        assert '한글 로그' in (tmp_path / 'logs/dugout_atlas.log').read_text(encoding='utf-8')
    finally:
        for handler in root.handlers:
            handler.close()


def test_name_loading_does_not_create_override_parent(tmp_path, monkeypatch):
    from services.player_name_localization import PlayerNameLocalizer
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'unused'))
    localizer = PlayerNameLocalizer(cache_path=tmp_path / 'missing.json')
    assert localizer.players
    assert not (tmp_path / 'unused').exists()
