from __future__ import annotations

from pathlib import Path

import pandas as pd

from database.sqlite_manager import SQLiteManager
from services.fangraphs_service import FanGraphsService


def _db(tmp_path: Path) -> SQLiteManager:
    schema = Path(__file__).resolve().parents[1] / "database" / "schema.sql"
    return SQLiteManager(tmp_path / "test.sqlite3", schema)


def test_fangraphs_custom_date_range_uses_month_1000() -> None:
    params = FanGraphsService._api_params(
        2026,
        2026,
        False,
        start_date="2026-08-01",
        end_date="2026-08-31",
        ind=0,
    )
    assert params["season"] == 2026
    assert params["season1"] == 2026
    assert params["startdate"] == "2026-08-01"
    assert params["enddate"] == "2026-08-31"
    assert params["month"] == "1000"
    assert params["ind"] == "0"


def test_fangraphs_direct_http_uses_mobile_app_user_agent(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def raise_for_status() -> None:
            return None

        @staticmethod
        def json() -> dict[str, object]:
            return {"data": []}

    def fake_get(url, *, params, headers, timeout):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse()

    import services.fangraphs_service as fg_module

    monkeypatch.setattr(fg_module.requests, "get", fake_get)
    payload = FanGraphsService._request_json(
        "https://www.fangraphs.com/api/leaders/major-league/data",
        {"season": 2026},
    )
    assert payload == {"data": []}
    assert captured["headers"]["User-Agent"] == "okhttp/4.12.0"


def test_fangraphs_monthly_trend_uses_exact_calendar_ranges(
    tmp_path: Path, monkeypatch
) -> None:
    service = FanGraphsService(_db(tmp_path))
    calls: list[tuple[str, str]] = []

    def fake_fetch(
        _start: int,
        _end: int,
        _pitcher: bool,
        *,
        start_date: str = "",
        end_date: str = "",
        ind: int = 1,
    ) -> pd.DataFrame:
        calls.append((start_date, end_date))
        return pd.DataFrame(
            [
                {
                    "xMLBAMID": 592450,
                    "playerid": 15640,
                    "Name": "Aaron Judge",
                    "WAR": 1.0,
                    "wRC+": 150,
                }
            ]
        )

    monkeypatch.setattr(service, "_fetch_api", fake_fetch)
    rows = service.get_period_history(592450, "Aaron Judge", 2025, False, "monthly")
    assert len(rows) == 8
    assert rows[0]["Period"] == "2025-03"
    assert rows[-1]["Period"] == "2025-10"
    assert calls[0] == ("2025-03-01", "2025-03-31")
    assert calls[-1] == ("2025-10-01", "2025-10-31")


def test_fangraphs_daily_trend_is_bounded_to_recent_14_games(
    tmp_path: Path, monkeypatch
) -> None:
    service = FanGraphsService(_db(tmp_path))
    game_dates = pd.date_range("2026-04-01", periods=20, freq="D")
    frame = pd.DataFrame({"Date": [value.strftime("%Y-%m-%d") for value in game_dates]})
    monkeypatch.setattr(service, "_game_log_frame", lambda *_args: frame)

    def fake_fetch(
        _start: int,
        _end: int,
        _pitcher: bool,
        *,
        start_date: str = "",
        end_date: str = "",
        ind: int = 1,
    ) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "xMLBAMID": 592450,
                    "playerid": 15640,
                    "Name": "Aaron Judge",
                    "WAR": 0.1,
                    "wRC+": 175,
                }
            ]
        )

    monkeypatch.setattr(service, "_fetch_api", fake_fetch)
    rows = service.get_period_history(592450, "Aaron Judge", 2026, False, "daily")
    assert len(rows) == 14
    assert rows[0]["Period"] == "2026-04-07"
    assert rows[-1]["Period"] == "2026-04-20"
