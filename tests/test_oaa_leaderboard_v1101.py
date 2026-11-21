from __future__ import annotations

from pathlib import Path

import pandas as pd

from database.sqlite_manager import SQLiteManager
from services.statcast_service import StatcastService


def _db(tmp_path: Path) -> SQLiteManager:
    schema = Path(__file__).resolve().parents[1] / "database" / "schema.sql"
    return SQLiteManager(tmp_path / "test.sqlite3", schema)


def test_oaa_comes_from_official_fielder_all_positions_leaderboard(
    tmp_path: Path, monkeypatch
) -> None:
    service = StatcastService(_db(tmp_path))
    calls: list[tuple[str, dict, object]] = []

    def fake_savant(url: str, params: dict, *, fallback=None):
        calls.append((url, params, fallback))
        if "outs_above_average" in url:
            return pd.DataFrame(
                [
                    {
                        "player_id": 12345,
                        "outs_above_average": 7.375,
                        "fielding_runs_prevented": 5.0,
                    }
                ]
            )
        return pd.DataFrame()

    monkeypatch.setattr(service, "_savant_csv", fake_savant)
    result = service.get_defense(12345, 2026, "SS")

    assert result["OAA"] == 7.375
    assert result["Runs Prevented"] == 5.0
    oaa_call = next(call for call in calls if "outs_above_average" in call[0])
    assert oaa_call[1]["type"] == "Fielder"
    assert oaa_call[1]["pos"] == ""
    assert oaa_call[1]["startYear"] == 2026
    assert oaa_call[1]["endYear"] == 2026
    assert oaa_call[1]["csv"] == "true"
    assert oaa_call[2] is None
    assert any(
        "OAA Leaderboard — Fielder / All Positions" in source["name"]
        for source in result["_sources"]
    )


def test_oaa_never_falls_back_to_runs_prevented_or_pybaseball(
    tmp_path: Path, monkeypatch
) -> None:
    service = StatcastService(_db(tmp_path))

    def fake_savant(url: str, params: dict, *, fallback=None):
        if "outs_above_average" in url:
            assert fallback is None
            return pd.DataFrame(
                [{"player_id": 12345, "fielding_runs_prevented": 9.25}]
            )
        return pd.DataFrame()

    def pybaseball_must_not_supply_oaa():
        raise AssertionError("pybaseball must not be used as an OAA fallback")

    monkeypatch.setattr(service, "_savant_csv", fake_savant)
    monkeypatch.setattr(service, "_pybaseball", pybaseball_must_not_supply_oaa)
    result = service.get_defense(12345, 2026, "CF")

    assert result.get("OAA") is None
    assert result["Runs Prevented"] == 9.25
    assert any("did not contain an OAA column" in msg for msg in result["_errors"])


def test_catcher_still_queries_oaa_leaderboard_instead_of_skipping(
    tmp_path: Path, monkeypatch
) -> None:
    service = StatcastService(_db(tmp_path))
    oaa_requested = False

    def fake_savant(url: str, params: dict, *, fallback=None):
        nonlocal oaa_requested
        if "outs_above_average" in url:
            oaa_requested = True
            return pd.DataFrame([{"player_id": 54321, "oaa": 0.625}])
        return pd.DataFrame()

    monkeypatch.setattr(service, "_savant_csv", fake_savant)
    result = service.get_defense(54321, 2026, "C")

    assert oaa_requested is True
    assert result["OAA"] == 0.625
