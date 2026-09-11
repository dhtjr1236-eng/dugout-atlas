from __future__ import annotations

from pathlib import Path

import pandas as pd

import services.bref_service as bref_module
from database.sqlite_manager import SQLiteManager
from services.base_http import HttpError
from services.bref_service import BaseballReferenceService
from services.fangraphs_service import FanGraphsService
from services.statcast_service import StatcastService


def _db(tmp_path: Path) -> SQLiteManager:
    schema = Path(__file__).resolve().parents[1] / "database" / "schema.sql"
    return SQLiteManager(tmp_path / "test.sqlite3", schema)


def test_fangraphs_matches_mlbam_without_chadwick_lookup(tmp_path: Path) -> None:
    service = FanGraphsService(_db(tmp_path))
    frame = pd.DataFrame(
        [{"xMLBAMID": 592450, "Name": "Aaron Judge", "WAR": 7.5, "wRC+": 180}]
    )
    row = service._find_player_row(frame, 592450, "Aaron Judge")
    assert row is not None
    assert row["WAR"] == 7.5


def test_fangraphs_name_fallback_and_percent_normalization(tmp_path: Path) -> None:
    service = FanGraphsService(_db(tmp_path))
    service._fangraphs_id = lambda _player_id: None  # type: ignore[method-assign]
    frame = pd.DataFrame([{"Name": "José Ramírez", "WAR": 5.0}])
    row = service._find_player_row(frame, 999999, "Jose Ramirez")
    assert row is not None
    assert service._pct(0.257) == 25.7
    assert service._pct("31.2%") == 31.2


def test_bref_direct_daily_file_is_primary_and_uses_mlbam(tmp_path: Path, monkeypatch) -> None:
    service = BaseballReferenceService(_db(tmp_path))
    BaseballReferenceService._daily_cache.clear()

    csv = (
        "name_common,mlb_ID,player_ID,year_ID,team_ID,WAR,OPS_plus\n"
        "Test Player,12345,testpl01,2026,NYY,4.2,137\n"
    )
    monkeypatch.setattr(
        bref_module,
        "sync_get_text",
        lambda _url, **_kwargs: csv,
    )
    # Do not let this unit test make the second player-page request.
    monkeypatch.setattr(service, "_player_page_row", lambda *_args: (None, "player"))

    result = service.get_bwar(12345, 2026, False, "Test Player")
    assert result["bWAR"] == 4.2
    assert result["OPS+"] == 137
    assert result["_status"] == "ok"
    assert "war_daily_bat.txt" in result["_sources"][0]["url"]


def test_bref_name_fallback_when_mlbam_id_is_missing(tmp_path: Path, monkeypatch) -> None:
    service = BaseballReferenceService(_db(tmp_path))
    frame = pd.DataFrame(
        [
            {
                "name_common": "José Ramírez",
                "mlb_ID": None,
                "player_ID": None,
                "year_ID": 2026,
                "WAR": 5.4,
                "OPS_plus": 151,
            }
        ]
    )
    monkeypatch.setattr(service, "_war_frame", lambda _pitcher: frame)
    monkeypatch.setattr(service, "_bbref_id", lambda _pid: None)
    monkeypatch.setattr(service, "_search_player_page_row", lambda *_args: (None, "search"))
    result = service.get_bwar(608070, 2026, False, "Jose Ramirez")
    assert result["bWAR"] == 5.4
    assert result["OPS+"] == 151


def test_bref_player_page_parser_uses_exact_season_and_role(tmp_path: Path, monkeypatch) -> None:
    service = BaseballReferenceService(_db(tmp_path))
    html = """
    <html><body>
    <table><thead><tr><th>Season</th><th>Team</th><th>WAR</th><th>OPS+</th><th>PA</th></tr></thead>
    <tbody>
      <tr><td>2025</td><td>NYY</td><td>8.1</td><td>180</td><td>700</td></tr>
      <tr><td>2026</td><td>NYY</td><td>6.3</td><td>166</td><td>580</td></tr>
    </tbody></table>
    <table><thead><tr><th>Season</th><th>WAR</th><th>ERA+</th><th>IP</th></tr></thead>
    <tbody><tr><td>2026</td><td>1.2</td><td>130</td><td>40.0</td></tr></tbody></table>
    </body></html>
    """
    monkeypatch.setattr(service, "_bref_get_text", lambda _url: html)
    row, url = service._player_page_row("judgeaa01", 2026, False)
    assert row is not None
    assert float(row["WAR"]) == 6.3
    assert int(row["OPS+"]) == 166
    assert url.endswith("/players/j/judgeaa01.shtml")


def test_bref_player_page_overrides_daily_value_for_auditable_display(
    tmp_path: Path, monkeypatch
) -> None:
    service = BaseballReferenceService(_db(tmp_path))
    daily = pd.DataFrame(
        [
            {
                "name_common": "Test Player",
                "mlb_ID": 12345,
                "player_ID": "testpl01",
                "year_ID": 2026,
                "team_ID": "NYY",
                "WAR": 4.1,
                "OPS_plus": 135,
            }
        ]
    )
    page_row = pd.Series({"Season": 2026, "Team": "NYY", "WAR": 4.3, "OPS+": 139})
    monkeypatch.setattr(service, "_war_frame", lambda _pitcher: daily)
    monkeypatch.setattr(
        service,
        "_player_page_row",
        lambda *_args: (page_row, "https://www.baseball-reference.com/players/t/testpl01.shtml"),
    )

    result = service.get_bwar(12345, 2026, False, "Test Player")
    assert result["bWAR"] == 4.3
    assert result["OPS+"] == 139
    assert any(row["name"] == "Baseball-Reference Player Page" for row in result["_sources"])


def test_bref_rate_limited_player_page_keeps_daily_bwar(tmp_path: Path, monkeypatch) -> None:
    service = BaseballReferenceService(_db(tmp_path))
    daily = pd.DataFrame(
        [
            {
                "name_common": "Test Pitcher",
                "mlb_ID": 54321,
                "player_ID": "testpi01",
                "year_ID": 2026,
                "team_ID": "BOS",
                "WAR": 3.7,
                "ERA_plus": 128,
            }
        ]
    )
    monkeypatch.setattr(service, "_war_frame", lambda _pitcher: daily)

    def blocked(*_args):
        service._fetch_errors.append("Baseball-Reference rate limited this IP (HTTP 429).")
        return None, "https://www.baseball-reference.com/players/t/testpi01.shtml"

    monkeypatch.setattr(service, "_player_page_row", blocked)
    result = service.get_bwar(54321, 2026, True, "Test Pitcher")
    assert result["bWAR"] == 3.7
    assert result["ERA+"] == 128
    assert any("429" in message for message in result["_errors"])


def test_bref_name_search_fallback_parses_redirected_player_html(
    tmp_path: Path, monkeypatch
) -> None:
    service = BaseballReferenceService(_db(tmp_path))
    html = """
    <html><body><table>
    <thead><tr><th>Season</th><th>Team</th><th>WAR</th><th>OPS+</th></tr></thead>
    <tbody><tr><td>2026</td><td>NYY</td><td>5.1</td><td>144</td></tr></tbody>
    </table></body></html>
    """
    monkeypatch.setattr(service, "_bref_get_text", lambda url: html)
    row, url = service._search_player_page_row("Aaron Judge", 2026, False)
    assert row is not None
    assert float(row["WAR"]) == 5.1
    assert "search.fcgi?search=Aaron+Judge" in url


def test_bref_traded_player_page_prefers_aggregate_row(tmp_path: Path) -> None:
    service = BaseballReferenceService(_db(tmp_path))
    rows = pd.DataFrame(
        [
            {"Season": 2026, "Team": "NYY", "PA": 200, "WAR": 1.1, "OPS+": 110},
            {"Season": 2026, "Team": "2TM", "PA": 500, "WAR": 4.6, "OPS+": 141},
            {"Season": 2026, "Team": "SFG", "PA": 300, "WAR": 3.5, "OPS+": 150},
        ]
    )
    row = service._season_total_row(rows, False)
    assert row is not None
    assert row["Team"] == "2TM"
    assert row["WAR"] == 4.6


def test_bref_commented_table_parser(tmp_path: Path) -> None:
    _ = BaseballReferenceService(_db(tmp_path))
    html = """
    <html><body><!--
    <table id="standard_batting">
      <thead><tr><th>Season</th><th>WAR</th><th>OPS+</th></tr></thead>
      <tbody><tr><td>2026</td><td>5.7</td><td>155</td></tr></tbody>
    </table>
    --></body></html>
    """
    frames = BaseballReferenceService._tables_from_html(html)
    assert len(frames) == 1
    assert float(frames[0].iloc[0]["WAR"]) == 5.7


def test_velocity_history_is_monthly_statcast_and_independent(tmp_path: Path, monkeypatch) -> None:
    service = StatcastService(_db(tmp_path))

    frame = pd.DataFrame(
        [
            {"game_date": "2026-04-05", "pitch_type": "FF", "release_speed": 95.0},
            {"game_date": "2026-04-10", "pitch_type": "FF", "release_speed": 97.0},
            {"game_date": "2026-05-03", "pitch_type": "FF", "release_speed": 98.0},
            {"game_date": "2026-05-04", "pitch_type": "SL", "release_speed": 86.0},
        ]
    )

    class FakePybaseball:
        @staticmethod
        def statcast_pitcher(_start: str, _end: str, _player_id: int):
            return frame

    monkeypatch.setattr(service, "_pybaseball", lambda: FakePybaseball())
    rows = service.get_velocity_history(12345, 2026)
    assert [row["Period"] for row in rows] == ["2026-04", "2026-05"]
    assert rows[0]["Avg Velocity"] == 96.0
    assert rows[1]["Avg Velocity"] == 98.0
    assert rows[0]["Pitch"] == "Four-Seam Fastball"


def test_fangraphs_history_uses_correct_start_end_params(tmp_path: Path, monkeypatch) -> None:
    service = FanGraphsService(_db(tmp_path))
    captured = {}

    def fake_get(_url, params=None):
        captured.update(params or {})
        return '{"data": []}'

    import services.fangraphs_service as fg_module

    monkeypatch.setattr(fg_module, "sync_get_text", fake_get)
    service._fetch_api(2021, 2026, False)
    assert captured["season"] == 2026
    assert captured["season1"] == 2021


def test_history_falls_back_when_direct_response_has_no_season(tmp_path: Path, monkeypatch) -> None:
    service = FanGraphsService(_db(tmp_path))
    monkeypatch.setattr(
        service,
        "_fetch_api",
        lambda *_args: pd.DataFrame(
            [{"xMLBAMID": 592450, "Name": "Aaron Judge", "WAR": 20.0}]
        ),
    )

    class FakePybaseball:
        @staticmethod
        def batting_stats(_start: int, _end: int, qual: int = 0, ind: int = 1):
            return pd.DataFrame(
                [
                    {"IDfg": 15640, "Name": "Aaron Judge", "Season": 2025, "WAR": 9.0, "wRC+": 170},
                    {"IDfg": 15640, "Name": "Aaron Judge", "Season": 2026, "WAR": 8.0, "wRC+": 165},
                ]
            )

    monkeypatch.setattr(service, "_pybaseball", lambda: FakePybaseball())
    monkeypatch.setattr(service, "_fangraphs_id", lambda _pid: 15640)
    rows = service.get_history(592450, "Aaron Judge", 2025, 2026, False)
    assert [row["Season"] for row in rows] == [2025, 2026]
    assert [row["WAR"] for row in rows] == [9.0, 8.0]
    assert [row["wRC+"] for row in rows] == [170, 165]


def test_current_oaa_uses_strict_oaa_column_not_runs_prevented(
    tmp_path: Path, monkeypatch
) -> None:
    service = StatcastService(_db(tmp_path))

    def fake_savant(url, _params, fallback=None):
        if "outs_above_average" in url:
            assert fallback is None
            return pd.DataFrame(
                [
                    {
                        "player_id": 12345,
                        "outs_above_average": 7,
                        "fielding_runs_prevented": 5,
                    }
                ]
            )
        return pd.DataFrame()

    monkeypatch.setattr(service, "_savant_csv", fake_savant)
    result = service.get_defense(12345, 2026, "SS")
    assert result["OAA"] == 7.0
    assert result["Runs Prevented"] == 5.0
    assert result["OAA"] != result["Runs Prevented"]
    assert "pos=" in result["_sources"][0]["url"]


def test_current_oaa_never_substitutes_runs_prevented(
    tmp_path: Path, monkeypatch
) -> None:
    service = StatcastService(_db(tmp_path))

    def fake_savant(url, _params, fallback=None):
        if "outs_above_average" in url:
            return pd.DataFrame([{"player_id": 12345, "fielding_runs_prevented": 9}])
        return pd.DataFrame()

    monkeypatch.setattr(service, "_savant_csv", fake_savant)
    result = service.get_defense(12345, 2026, "SS")
    assert result.get("OAA") is None
    assert result.get("Runs Prevented") == 9.0
    assert any("did not contain an OAA column" in msg for msg in result["_errors"])


def test_oaa_accepts_official_n_outs_above_average_alias(tmp_path: Path, monkeypatch) -> None:
    service = StatcastService(_db(tmp_path))

    def fake_savant(url, _params, fallback=None):
        if "outs_above_average" in url:
            return pd.DataFrame([{"player_id": 12345, "n_outs_above_average": 11}])
        return pd.DataFrame()

    monkeypatch.setattr(service, "_savant_csv", fake_savant)
    result = service.get_defense(12345, 2026, "CF")
    assert result["OAA"] == 11.0


def test_bref_local_zip_import_supplies_bwar_without_network(tmp_path: Path, monkeypatch) -> None:
    import zipfile
    from services.bref_local_store import BRefLocalStore

    service = BaseballReferenceService(_db(tmp_path))
    service.local_store = BRefLocalStore(tmp_path / "bref")
    BaseballReferenceService.reset_network_breaker()
    BaseballReferenceService._daily_cache.clear()

    batting = pd.DataFrame(
        [
            {
                "name_common": "Jung Hoo Lee",
                "mlb_ID": 808982,
                "player_ID": "leeju01",
                "year_ID": 2026,
                "team_ID": "SFG",
                "stint_ID": 1,
                "PA": 500,
                "runs_above_avg_off": 8.0,
                "WAR": 3.4,
            }
        ]
    )
    pitching = pd.DataFrame(
        [
            {
                "name_common": "Test Pitcher",
                "mlb_ID": 123456,
                "player_ID": "testpi01",
                "year_ID": 2026,
                "team_ID": "SFG",
                "GS": 20,
                "RA": 50,
                "ERA_plus": 125,
                "WAR": 2.8,
            }
        ]
    )
    zip_path = tmp_path / "war_archive-2026-09-08.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("war_daily_bat.txt", batting.to_csv(index=False))
        archive.writestr("war_daily_pitch.txt", pitching.to_csv(index=False))

    imported = service.import_local_file(zip_path)
    assert imported["batting_rows"] == 1
    assert imported["pitching_rows"] == 1

    def network_must_not_run(_url: str) -> str:
        raise AssertionError("B-Ref network must not be used when local snapshot exists")

    monkeypatch.setattr(service, "_bref_get_text", network_must_not_run)
    result = service.get_bwar(808982, 2026, False, "Jung Hoo Lee")
    assert result["bWAR"] == 3.4
    assert result["_status"] == "partial"  # OPS+ is not guaranteed in WAR file.
    assert "local import" in result["_sources"][0]["name"]


def test_bref_403_trips_breaker_and_skips_pybaseball_transport(
    tmp_path: Path, monkeypatch
) -> None:
    import services.bref_service as bref_module
    from services.bref_local_store import BRefLocalStore

    service = BaseballReferenceService(_db(tmp_path))
    service.local_store = BRefLocalStore(tmp_path / "bref")
    BaseballReferenceService.reset_network_breaker()
    BaseballReferenceService._daily_cache.clear()

    def blocked(*_args, **_kwargs):
        raise HttpError("403 Client Error: Forbidden")

    monkeypatch.setattr(bref_module, "sync_get_text", blocked)

    class NeverPybaseball:
        pass

    def must_not_call_pybaseball():
        raise AssertionError("pybaseball calls the same blocked B-Ref endpoint")

    monkeypatch.setattr(service, "_pybaseball", must_not_call_pybaseball)
    frame = service._daily_war_frame(False)
    assert frame.empty
    assert BaseballReferenceService._network_blocked()
    assert any("HTTP 403" in message for message in service._fetch_errors)
    BaseballReferenceService.reset_network_breaker()


def test_bref_single_txt_import_is_classified_as_batting(tmp_path: Path) -> None:
    from services.bref_local_store import BRefLocalStore

    store = BRefLocalStore(tmp_path / "bref")
    frame = pd.DataFrame(
        [
            {
                "name_common": "Example Hitter",
                "mlb_ID": 999,
                "player_ID": "example01",
                "year_ID": 2026,
                "PA": 400,
                "runs_above_avg_off": 10,
                "WAR": 4.0,
            }
        ]
    )
    path = tmp_path / "war_daily_bat.txt"
    frame.to_csv(path, index=False)
    result = store.import_path(path)
    assert result.batting_rows == 1
    assert result.pitching_rows == 0
    assert float(store.load(False).iloc[0]["WAR"]) == 4.0
