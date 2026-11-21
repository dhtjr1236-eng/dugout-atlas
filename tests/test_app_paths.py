from __future__ import annotations

import sys
from pathlib import Path
import pytest
from config import paths


def test_development_resource(monkeypatch):
    monkeypatch.delattr(sys, 'frozen', raising=False)
    assert paths.resource_path('config', 'translations.json') == Path(__file__).resolve().parents[1] / 'config/translations.json'


def test_frozen_bundle(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
    assert paths.is_frozen()
    assert paths.bundle_dir() == tmp_path
    assert paths.resource_path('config/theme.qss') == tmp_path / 'config/theme.qss'


def test_user_root(monkeypatch, tmp_path):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'local'))
    expected = tmp_path / 'local/Dugout Atlas'
    assert paths.user_data_dir() == expected
    assert expected.is_dir()
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    assert paths.user_data_dir() == expected


def test_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv('LOCALAPPDATA', raising=False)
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    assert paths.user_data_dir() == tmp_path / 'AppData/Local/Dugout Atlas'


@pytest.mark.parametrize('part', ['../outside', '/outside', 'C:/outside', r'C:\outside', r'..\outside', '//server/share', '', '.', 'foo/../bar', 'foo.', 'foo ', 'file:stream', 'NUL', 'CON.txt', 'foo*', 'a\x00b'])
def test_escape_rejected(monkeypatch, tmp_path, part):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    with pytest.raises(ValueError):
        paths.data_path(part)


def test_symlink_escape(monkeypatch, tmp_path):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'local'))
    root = paths.user_data_dir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    try:
        (root / 'link').symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('Symlinks require platform permission')
    with pytest.raises(ValueError):
        paths.data_path('link', 'secret')


def test_directories_and_lazy_path(monkeypatch, tmp_path):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'local'))
    target = paths.data_path('config', 'preferences.ini', create_parent=False)
    assert not target.parent.exists()
    for helper, name in [(paths.cache_dir, 'cache'), (paths.database_dir, 'database'), (paths.logs_dir, 'logs'), (paths.exports_dir, 'exports')]:
        result = helper()
        assert result == tmp_path / 'local/Dugout Atlas' / name
        assert result.is_dir()
    assert paths.data_path('config', 'preferences.ini').parent.is_dir()


def test_database_creates_parent(tmp_path):
    from database.sqlite_manager import SQLiteManager
    target = tmp_path / 'nested' / 'database' / 'test.sqlite3'
    db = SQLiteManager(target)
    with db.connection() as connection:
        assert connection.execute('SELECT 1').fetchone()[0] == 1
