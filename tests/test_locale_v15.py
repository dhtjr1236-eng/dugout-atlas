from __future__ import annotations

from types import SimpleNamespace
from services.player_name_localization import extract_mlb_locale_player_name, katakana_to_hangul
from services.team_localization import apply_team_ref, localized_team_name

def test_mlb_japan_seo_title_is_stripped() -> None:
    page='<meta property="og:title" content="ムーキー ベッツ Stats, Age, Position, Height, Weight, Fantasy News">'
    assert extract_mlb_locale_player_name(page,"ja") == "ムーキー ベッツ"

def test_katakana_fallback() -> None:
    assert katakana_to_hangul("ムーキー ベッツ") == "무키 베츠"

def test_team_localization() -> None:
    assert localized_team_name(119,"Los Angeles Dodgers","ko") == "LA 다저스"
    team=SimpleNamespace(id=137,name="San Francisco Giants",abbreviation="SF")
    apply_team_ref(team,"ja")
    assert team.name == "サンフランシスコ・ジャイアンツ"
    assert team.abbreviation == "ジャイアンツ"
