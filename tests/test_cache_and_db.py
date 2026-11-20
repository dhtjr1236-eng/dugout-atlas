from pathlib import Path

from cache.json_cache import JsonCache
from database.sqlite_manager import SQLiteManager


def test_json_cache_round_trip(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path)
    cache.set("demo", "aaron-judge-2026", {"wRC+": 175})
    assert cache.get("demo", "aaron-judge-2026", ttl_days=30) == {"wRC+": 175}


def test_sqlite_player_stats_round_trip(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite3"
    schema_path = Path(__file__).resolve().parents[1] / "database" / "schema.sql"
    db = SQLiteManager(db_path=db_path, schema_path=schema_path)
    db.set_player_stats(592450, "fangraphs", 2026, "batter", {"fWAR": 7.1})
    value = db.get_player_stats(592450, "fangraphs", 2026, "batter", ttl_days=30)
    assert value == {"fWAR": 7.1}


def test_sqlite_pitch_stats_round_trip(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite3"
    schema_path = Path(__file__).resolve().parents[1] / "database" / "schema.sql"
    db = SQLiteManager(db_path=db_path, schema_path=schema_path)
    rows = [{"pitch_type": "Four-Seam Fastball", "Usage %": 55.2}]
    db.set_pitch_stats(123, 2026, rows)
    assert db.get_pitch_stats(123, 2026, 30) == rows
