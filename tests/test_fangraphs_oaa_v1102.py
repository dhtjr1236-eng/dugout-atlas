from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from database.sqlite_manager import SQLiteManager
from services.fangraphs_fielding import defense_metrics, get_fangraphs_oaa
from services.fangraphs_service import FanGraphsService


def _db(tmp_path: Path) -> SQLiteManager:
    schema = Path(__file__).resolve().parents[1] / "database" / "schema.sql"
    return SQLiteManager(tmp_path / "test.sqlite3", schema)


def test_fangraphs_fielding_oaa_uses_fielding_leaderboard_and_preserves_decimal(
    tmp_path: Path, monkeypatch
) -> None:
    service = FanGraphsService(_db(tmp_path))
    captured = {}

    def fake_request(_url, params):
        captured.update(params)
        return {
            "data": [
                {
                    "xMLBAMID": 12345,
                    "Name": "Example Fielder",
                    "OAA": 7.6,
                }
            ]
        }

    monkeypatch.setattr(service, "_request_json", fake_request)
    result = get_fangraphs_oaa(service, 12345, "Example Fielder", 2026)

    assert result["FanGraphs OAA"] == 7.6
    assert captured["stats"] == "fld"
    assert captured["type"] == "1"
    assert captured["season"] == 2026
    assert captured["season1"] == 2026
    assert captured["qual"] == "0"
    assert "FanGraphs Fielding Leaderboard" in result["_source"]["name"]


def test_defense_metrics_contains_savant_and_fangraphs_oaa() -> None:
    bundle = SimpleNamespace(
        defense={
            "OAA": 8.0,
            "FanGraphs OAA": 7.6,
            "Runs Prevented": 6.0,
            "Fielding Run Value": 5.0,
            "Arm Value": 1.0,
        }
    )
    metrics = defense_metrics(bundle)
    assert len(metrics) == 5
    assert metrics[0][:2] == ("OAA", 8.0)
    assert metrics[1][:2] == ("FanGraphs OAA", 7.6)
