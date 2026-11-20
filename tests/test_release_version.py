"""Keep published version labels and runtime metadata aligned."""
from __future__ import annotations

from pathlib import Path
import tomllib

from config.settings import SETTINGS


def test_current_release_version_is_consistent():
    root = Path(__file__).resolve().parents[1]
    with (root / 'pyproject.toml').open('rb') as stream:
        version = tomllib.load(stream)['project']['version']
    assert version == SETTINGS.app_version == '1.92'
    assert f'Dugout-Atlas/{version}' in SETTINGS.user_agent
    readme = (root / 'README.md').read_text(encoding='utf-8')
    assert '# ⚾ Dugout Atlas' in readme
    assert f'/releases/download/v{version}/DugoutAtlas-v{version}-Setup.exe' in readme
    assert f'/releases/tag/v{version}' in readme
    assert (root / f'docs/PATCH_v{version}.md').is_file()
