from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from services.player_service import PlayerService


class _DummyDB:
    def __init__(self) -> None:
        self.rows: dict[tuple[int, str, int, str], dict] = {}

    def get_player_stats(self, player_id, source, season, group, _ttl):
        return self.rows.get((player_id, source, season, group))

    def set_player_stats(self, player_id, source, season, group, payload):
        self.rows[(player_id, source, season, group)] = payload


class _DummyPB:
    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame

    def statcast_pitcher(self, _start: str, _end: str, _player_id: int) -> pd.DataFrame:
        return self.frame.copy()


class _DummyStatcast:
    def __init__(self, frame: pd.DataFrame) -> None:
        self.pb = _DummyPB(frame)

    def _pybaseball(self):
        return self.pb

    @staticmethod
    def season_dates(season: int) -> tuple[str, str]:
        return f"{season}-03-01", f"{season}-11-30"

    @staticmethod
    def _aggregate_pitcher(frame: pd.DataFrame) -> dict:
        return {"Pitch Rows": len(frame)}

    @staticmethod
    def _pitch_whiff_percent(group: pd.DataFrame) -> float | None:
        return 50.0 if len(group) else None


def _service(frame: pd.DataFrame) -> PlayerService:
    service = object.__new__(PlayerService)
    service.db = _DummyDB()
    service.statcast = _DummyStatcast(frame)
    return service


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "game_date": ["2026-08-31", "2026-09-10", "2026-09-10", "2026-09-14"],
            "pitch_type": ["FF", "FF", "SL", "FF"],
            "release_speed": [96.0, 97.0, 86.0, 98.0],
            "release_spin_rate": [2400, 2450, 2500, 2475],
            "delta_run_exp": [0.1, -0.1, 0.2, -0.2],
            "description": ["called_strike", "swinging_strike", "foul", "swinging_strike"],
        }
    )


def test_pitcher_monthly_statcast_uses_latest_active_month() -> None:
    payload = _service(_frame()).get_pitcher_statcast_period(123, 2026, "monthly")

    assert payload["label"] == "2026-09"
    assert payload["statcast"]["Pitch Rows"] == 3
    assert payload["pitch_table"]
    assert [row["Period"] for row in payload["velocity_history"]] == ["09-10", "09-14"]


def test_pitcher_daily_statcast_uses_latest_appearance_date() -> None:
    payload = _service(_frame()).get_pitcher_statcast_period(123, 2026, "daily")

    assert payload["label"] == "2026-09-14"
    assert payload["statcast"]["Pitch Rows"] == 1
    assert payload["velocity_history"][0]["Period"] == "2026-09-14"


def test_compare_metric_contract_keeps_pitcher_and_hitter_roles_distinct() -> None:
    # This guards the data contract used by CompareView without constructing a Qt app.
    hitter = SimpleNamespace(profile=SimpleNamespace(is_pitcher=False))
    pitcher = SimpleNamespace(profile=SimpleNamespace(is_pitcher=True))

    from ui.compare_view import CompareView

    assert "wRC+" in CompareView._labels_for(hitter, hitter)
    assert "ERA" in CompareView._labels_for(pitcher, pitcher)
    assert CompareView._labels_for(hitter, pitcher) == [
        "fWAR",
        "bWAR",
        "BB%",
        "K%",
        "xBA",
        "xSLG",
        "xwOBA",
    ]
