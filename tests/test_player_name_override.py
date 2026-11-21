from __future__ import annotations

import json
import pytest
from services.player_name_localization import PlayerNameLocalizer


def localizer(tmp_path, override=None):
    seed = tmp_path / 'seed.json'
    seed.write_text(json.dumps({'players': [{'en': 'Test Player', 'ko': '기본', 'ja': '基本'}]}), encoding='utf-8')
    target = tmp_path / 'override.json'
    if override is not None:
        target.write_text(override, encoding='utf-8')
    return PlayerNameLocalizer(seed, tmp_path / 'cache.json', target)


def test_missing_override(tmp_path):
    assert localizer(tmp_path).display_name(1, 'Test Player', 'ko') == '기본'


def test_override_wins_over_seed_and_cache(tmp_path):
    item = localizer(tmp_path, json.dumps({'players': [{'en': 'Test Player', 'ko': '수정'}]}))
    item.cache = {'1': {'ko': '캐시'}}
    assert item.display_name(1, 'Test Player', 'ko') == '수정'
    assert item.display_name(1, 'Test Player', 'ja') == '基本'


@pytest.mark.parametrize('payload', ['{', '[]', '{}', '{"players":{}}', '{"players":[{"en":"Test Player","ko":2}]}', '{"players":[{"en":"Test Player","aliases":3}]}'])
def test_invalid_override_falls_back(tmp_path, caplog, payload):
    assert localizer(tmp_path, payload).display_name(1, 'Test Player', 'ko') == '기본'
    assert 'override' in caplog.text
