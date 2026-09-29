from __future__ import annotations

import json
from pathlib import Path
from services.player_name_localization import PlayerNameLocalizer, extract_mlb_locale_player_name

SEED = Path(__file__).resolve().parents[1] / "config" / "player_names_seed.json"

def loc(tmp_path: Path) -> PlayerNameLocalizer:
    return PlayerNameLocalizer(SEED, tmp_path / "cache.json")

def test_seed_preserves_original_countries_and_adds_user_names() -> None:
    rows = json.loads(SEED.read_text(encoding="utf-8"))["players"]
    assert len(rows) == 113
    assert sum(r.get("display_source") == "user-request-2026-09-28" for r in rows) == 101
    assert sum(r.get("country") == "KR" for r in rows) == 6
    assert sum(r.get("country") == "JP" for r in rows) == 15
    assert sum(r.get("country") == "TW" for r in rows) == 3

def test_jung_hoo_lee_japanese_is_exact_and_cache_cannot_override(tmp_path: Path) -> None:
    x = loc(tmp_path)
    x.cache = {"808982": {"en": "Jung Hoo Lee", "ja": "イ イ・ジョンフ"}}
    assert x.display_name(808982, "Jung Hoo Lee", "ja") == "李政厚"

def test_jung_hoo_replacement_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    x = loc(tmp_path)
    monkeypatch.setattr("services.player_name_localization.read_preferences", lambda: {"language": "ja"})
    pairs = x.replacement_pairs()
    assert ("ジョンフ", "イ・ジョンフ") not in pairs
    value = "イ・ジョンフ"
    for source, target in pairs: value = value.replace(source, target)
    assert value == "李政厚"

def test_hye_seong_kim_2026_team_is_lad(tmp_path: Path) -> None:
    assert loc(tmp_path).display_team("Hye-Seong Kim", "", 2026) == "LAD"

def test_tsung_che_cheng_korean_name(tmp_path: Path) -> None:
    assert loc(tmp_path).display_name(0, "Tsung-Che Cheng", "ko") == "정쭝저"

def test_localized_aliases_resolve_to_english_identity(tmp_path: Path) -> None:
    x = loc(tmp_path)
    assert x.alias_english_names("이정후") == ["Jung Hoo Lee"]
    assert x.alias_english_names("山本由伸") == ["Yoshinobu Yamamoto"]
    assert x.alias_english_names("정종저") == ["Tsung-Che Cheng"]

def test_extract_locale_titles() -> None:
    assert extract_mlb_locale_player_name('<meta property="og:title" content="이정후 통계 | MLB.com">', "ko") == "이정후"
    assert extract_mlb_locale_player_name('<meta property="og:title" content="山本 由伸 統計 | MLB.com">', "ja") == "山本 由伸"
