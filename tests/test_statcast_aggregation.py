import pandas as pd

from database.sqlite_manager import SQLiteManager
from services.statcast_service import StatcastService


def test_batter_aggregation(tmp_path) -> None:
    schema = __import__("pathlib").Path(__file__).resolve().parents[1] / "database" / "schema.sql"
    db = SQLiteManager(tmp_path / "test.sqlite3", schema)
    service = StatcastService(db)
    frame = pd.DataFrame(
        {
            "launch_speed": [100.0, 90.0, 110.0],
            "launch_angle": [15.0, 40.0, 20.0],
            "launch_speed_angle": [6, 3, 6],
            "estimated_ba_using_speedangle": [0.8, 0.1, 0.9],
            "estimated_slg_using_speedangle": [1.5, 0.2, 1.8],
            "estimated_woba_using_speedangle": [0.9, 0.1, 1.0],
            "description": ["hit_into_play", "swinging_strike", "ball"],
            "zone": [5, 12, 12],
        }
    )
    result = service._aggregate_batter(frame)
    assert round(result["Average Exit Velocity"], 1) == 100.0
    assert round(result["Hard Hit %"], 1) == 66.7
    assert round(result["Barrel %"], 1) == 66.7
    assert result["Whiff %"] == 50.0
    assert result["Chase %"] == 50.0


def test_oaa_uses_true_oaa_not_runs_prevented_and_all_positions(tmp_path, monkeypatch) -> None:
    schema = __import__("pathlib").Path(__file__).resolve().parents[1] / "database" / "schema.sql"
    db = SQLiteManager(tmp_path / "defense.sqlite3", schema)
    service = StatcastService(db)
    calls = []

    def fake_csv(url, params, fallback=None):
        calls.append((url, dict(params)))
        if "outs_above_average" in url:
            return pd.DataFrame([
                {
                    "player_id": 12345,
                    "outs_above_average": 8,
                    "fielding_runs_prevented": 6,
                }
            ])
        return pd.DataFrame([
            {
                "player_id": 12345,
                "fielding_run_value": 7,
                "arm_runs": 2,
            }
        ])

    monkeypatch.setattr(service, "_savant_csv", fake_csv)
    result = service.get_defense(12345, 2026, "CF")
    assert result["OAA"] == 8
    assert result["Runs Prevented"] == 6
    assert result["Fielding Run Value"] == 7
    assert result["Arm Value"] == 2
    assert calls[0][1]["pos"] == ""
