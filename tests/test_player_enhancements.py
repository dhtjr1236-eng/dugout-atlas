from __future__ import annotations

from services.player_enhancements import (
    _choose_default_season,
    _dedupe_and_rank,
    _extract_metrics,
    _merge_missing,
    _normalize_search_text,
)


def test_surname_query_matches_full_name() -> None:
    rows = [
        {"id": 1, "name": "Yusei Kikuchi"},
        {"id": 2, "name": "Yusei Sugano"},
    ]
    ranked = _dedupe_and_rank(rows, "kikuchi")
    assert ranked[0]["name"] == "Yusei Kikuchi"
    assert "kikuchi" in _normalize_search_text(ranked[0]["name"])


def test_current_season_is_default_when_available() -> None:
    assert _choose_default_season([2026, 2025, 2024], current_year=2026) == 2026


def test_last_season_is_default_when_current_is_missing() -> None:
    assert _choose_default_season([2025, 2024, 2023], current_year=2026) == 2025


def test_extract_metrics_keeps_wrc_plus_and_builds_ops() -> None:
    result = _extract_metrics({"AVG": ".276", "OBP": ".364", "SLG": ".448", "wRC+": 123})
    assert result["AVG"] == 0.276
    assert result["OPS"] == 0.812
    assert result["wRC+"] == 123.0


def test_mlb_slash_line_only_fills_missing_fangraphs_values() -> None:
    primary = {"AVG": 0.250, "OBP": None, "SLG": 0.450, "OPS": None, "wRC+": 110}
    fallback = {"AVG": 0.999, "OBP": 0.330, "SLG": 0.999, "OPS": 0.780, "wRC+": None}
    merged = _merge_missing(primary, fallback)
    assert merged["AVG"] == 0.250
    assert merged["OBP"] == 0.330
    assert merged["SLG"] == 0.450
    assert merged["OPS"] == 0.780
    assert merged["wRC+"] == 110
