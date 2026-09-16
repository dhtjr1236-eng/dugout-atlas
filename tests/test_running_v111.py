from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from database.sqlite_manager import SQLiteManager
from services.fangraphs_service import FanGraphsService
from services.running_metrics import get_baserunning, get_sprint_speed, running_metrics
from services.statcast_service import StatcastService


def _db(tmp_path: Path) -> SQLiteManager:
    schema = Path(__file__).resolve().parents[1] / "database" / "schema.sql"
    return SQLiteManager(tmp_path / "test.sqlite3", schema)


def test_sprint_speed_uses_savant_leaderboard_and_formats_unit(
    tmp_path: Path, monkeypatch
) -> None:
    service = StatcastService(_db(tmp_path))
    captured = {}

    def fake_savant(url, params, fallback=None):
        assert fallback is None
        captured["url"] = url
        captured.update(params)
        return pd.DataFrame(
            [{"player_id": 12345, "sprint_speed": 29.4}]
        )

    monkeypatch.setattr(service, "_savant_csv", fake_savant)
    result = get_sprint_speed(service, 12345, 2026)

    assert result["Sprint Speed"] == "29.4 ft/s"
    assert result["Sprint Speed Value"] == 29.4
    assert captured["min_season"] == 2026
    assert captured["max_season"] == 2026
    assert captured["min"] == 1
    assert "sprint_speed" in captured["url"]
    assert "Baseball Savant Sprint Speed Leaderboard" in result["_source"]["name"]


def test_baserunning_uses_fangraphs_sb_cs_and_calculates_success_rate(
    tmp_path: Path, monkeypatch
) -> None:
    service = FanGraphsService(_db(tmp_path))
    frame = pd.DataFrame(
        [
            {
                "xMLBAMID": 12345,
                "Name": "Example Runner",
                "SB": 24,
                "CS": 6,
            }
        ]
    )
    monkeypatch.setattr(service, "_season_frame", lambda _season, _pitcher: frame)

    result = get_baserunning(service, 12345, "Example Runner", 2026)

    assert result["SB"] == 24
    assert result["CS"] == 6
    assert result["SB Success %"] == 80.0
    assert "FanGraphs" in result["_source"]["name"]


def test_running_metrics_contains_four_requested_values() -> None:
    bundle = SimpleNamespace(
        statcast={"Sprint Speed": "28.7 ft/s"},
        fangraphs={"SB": 18, "CS": 3, "SB Success %": 85.7142857},
    )
    metrics = running_metrics(bundle)
    assert len(metrics) == 4
    assert metrics[0][:2] == ("Sprint Speed", "28.7 ft/s")
    assert metrics[1][:2] == ("SB", 18)
    assert metrics[2][:2] == ("CS", 3)
    assert metrics[3][0] == "SB Success %"
    assert metrics[3][2] is True
