from __future__ import annotations

import importlib
import json
import logging
import unicodedata
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import pandas as pd

from config.settings import SETTINGS
from database.sqlite_manager import SQLiteManager
from services.base_http import sync_get_text
from services.dataframe_utils import first_existing, row_to_dict
from services.freshness import source_ttl_days

LOGGER = logging.getLogger(__name__)
FG_LEADERS_URL = "https://www.fangraphs.com/api/leaders/major-league/data"


class FanGraphsService:
    """FanGraphs adapter with a resilient direct-API + pybaseball fallback.

    FanGraphs' current leaderboard is JSON-backed. We query it directly first,
    which lets us match on xMLBAMID and avoids depending on Chadwick ID lookup.
    pybaseball remains as a fallback so the service is not tied to one route.
    """

    def __init__(self, db: SQLiteManager) -> None:
        self.db = db

    @staticmethod
    def _pybaseball() -> Any:
        try:
            return importlib.import_module("pybaseball")
        except ImportError as exc:
            raise RuntimeError(
                "pybaseball is not installed. Run install.bat or pip install -r requirements.txt"
            ) from exc

    @staticmethod
    def _normalize_name(value: str) -> str:
        folded = unicodedata.normalize("NFKD", value)
        asciiish = "".join(ch for ch in folded if not unicodedata.combining(ch))
        return "".join(ch.casefold() for ch in asciiish if ch.isalnum())


    @staticmethod
    def _pct(value: Any) -> Any:
        """Normalize FanGraphs rate values to percentage points for the UI."""
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.endswith("%"):
                try:
                    return float(stripped[:-1])
                except ValueError:
                    return value
        try:
            number = float(value)
        except (TypeError, ValueError):
            return value
        return number * 100.0 if abs(number) <= 1.5 else number

    @staticmethod
    def _api_params(start: int, end: int, pitcher: bool) -> dict[str, Any]:
        return {
            "age": "",
            "pos": "all",
            "stats": "pit" if pitcher else "bat",
            "lg": "all",
            "qual": "0",
            "season": end,
            "season1": start,
            "startdate": "",
            "enddate": "",
            "month": "0",
            "team": "0",
            "pageitems": "10000",
            "pagenum": "1",
            "ind": "1",
            "rost": "0",
            "players": "",
            "type": "8",
            "postseason": "",
            "sortdir": "default",
            "sortstat": "WAR",
        }

    def _leaderboard_url(self, start: int, end: int, pitcher: bool) -> str:
        return f"{FG_LEADERS_URL}?{urlencode(self._api_params(start, end, pitcher))}"

    def _fetch_api(self, start: int, end: int, pitcher: bool) -> pd.DataFrame:
        params = self._api_params(start, end, pitcher)
        text = sync_get_text(FG_LEADERS_URL, params=params)
        payload = json.loads(text)
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        return pd.DataFrame(rows)

    def _fangraphs_id(self, player_id: int) -> int | None:
        """Best-effort lookup only; never let this prevent name/MLBAM fallback."""
        try:
            pb = self._pybaseball()
            frame = pb.playerid_reverse_lookup([int(player_id)], key_type="mlbam")
            if frame is None or frame.empty:
                return None
            raw = frame.iloc[0].get("key_fangraphs")
            return int(raw) if pd.notna(raw) else None
        except Exception as exc:
            LOGGER.info("FanGraphs ID lookup unavailable for %s: %s", player_id, exc)
            return None

    def _find_player_row(
        self, frame: pd.DataFrame, player_id: int, full_name: str
    ) -> pd.Series | None:
        if frame is None or frame.empty:
            return None

        # Current FanGraphs JSON leaderboards include MLBAM directly.
        for col in ("xMLBAMID", "MLBAMID", "mlbam_id", "key_mlbam"):
            if col in frame.columns:
                matches = frame[pd.to_numeric(frame[col], errors="coerce") == int(player_id)]
                if not matches.empty:
                    return matches.iloc[0]

        # FanGraphs ID is a secondary route; Chadwick lookup may itself fail.
        fg_id = self._fangraphs_id(player_id)
        if fg_id is not None:
            for col in ("IDfg", "playerid", "PlayerId"):
                if col in frame.columns:
                    matches = frame[pd.to_numeric(frame[col], errors="coerce") == fg_id]
                    if not matches.empty:
                        return matches.iloc[0]

        target = self._normalize_name(full_name)
        for col in ("Name", "PlayerName"):
            if col in frame.columns and target:
                matches = frame[
                    frame[col].astype(str).map(self._normalize_name) == target
                ]
                if not matches.empty:
                    return matches.iloc[0]
        return None

    def _season_frame(self, season: int, pitcher: bool) -> pd.DataFrame:
        try:
            frame = self._fetch_api(season, season, pitcher)
            if frame is not None and not frame.empty:
                return frame
        except Exception as exc:
            LOGGER.warning("Direct FanGraphs API failed: %s", exc)

        pb = self._pybaseball()
        func = pb.pitching_stats if pitcher else pb.batting_stats
        return func(season, season, qual=0, ind=1)

    def get_batter(self, player_id: int, full_name: str, season: int) -> dict[str, Any]:
        cached = self.db.get_player_stats(
            player_id, "fangraphs_v5", season, "batter", source_ttl_days(season)
        )
        if cached:
            return cached
        frame = self._season_frame(season, False)
        row = self._find_player_row(frame, player_id, full_name)
        if row is None:
            return {}
        raw = row_to_dict(row)
        result = {
            "fWAR": first_existing(raw, ("WAR",)),
            "wRC+": first_existing(raw, ("wRC+", "wRC_plus")),
            "OPS": first_existing(raw, ("OPS",)),
            "ISO": first_existing(raw, ("ISO",)),
            "BABIP": first_existing(raw, ("BABIP",)),
            "BB%": self._pct(first_existing(raw, ("BB%", "BB_pct"))),
            "K%": self._pct(first_existing(raw, ("K%", "K_pct"))),
            "wOBA": first_existing(raw, ("wOBA",)),
            "AVG": first_existing(raw, ("AVG",)),
            "OBP": first_existing(raw, ("OBP",)),
            "SLG": first_existing(raw, ("SLG",)),
            "PA": first_existing(raw, ("PA",)),
            "HR": first_existing(raw, ("HR",)),
            "RBI": first_existing(raw, ("RBI",)),
            "SB": first_existing(raw, ("SB",)),
            "_source": {
                "name": "FanGraphs Major League Leaderboards",
                "url": self._leaderboard_url(season, season, False),
                "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
            },
        }
        if any(value is not None for value in result.values()):
            self.db.set_player_stats(player_id, "fangraphs_v5", season, "batter", result)
        return result

    def get_pitcher(self, player_id: int, full_name: str, season: int) -> dict[str, Any]:
        cached = self.db.get_player_stats(
            player_id, "fangraphs_v5", season, "pitcher", source_ttl_days(season)
        )
        if cached:
            return cached
        frame = self._season_frame(season, True)
        row = self._find_player_row(frame, player_id, full_name)
        if row is None:
            return {}
        raw = row_to_dict(row)
        result = {
            "fWAR": first_existing(raw, ("WAR",)),
            "ERA": first_existing(raw, ("ERA",)),
            "FIP": first_existing(raw, ("FIP",)),
            "xFIP": first_existing(raw, ("xFIP",)),
            "WHIP": first_existing(raw, ("WHIP",)),
            "K%": self._pct(first_existing(raw, ("K%", "K_pct"))),
            "BB%": self._pct(first_existing(raw, ("BB%", "BB_pct"))),
            "_source": {
                "name": "FanGraphs Major League Leaderboards",
                "url": self._leaderboard_url(season, season, True),
                "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
            },
        }
        if any(value is not None for value in result.values()):
            self.db.set_player_stats(player_id, "fangraphs_v5", season, "pitcher", result)
        return result

    def _filter_player_rows(
        self, frame: pd.DataFrame, player_id: int, full_name: str
    ) -> pd.DataFrame:
        if frame is None or frame.empty:
            return pd.DataFrame()

        for col in ("xMLBAMID", "MLBAMID", "mlbam_id", "key_mlbam"):
            if col in frame.columns:
                matches = frame[
                    pd.to_numeric(frame[col], errors="coerce") == int(player_id)
                ]
                if not matches.empty:
                    return matches

        fg_id = self._fangraphs_id(player_id)
        if fg_id is not None:
            for col in ("IDfg", "playerid", "PlayerId"):
                if col in frame.columns:
                    matches = frame[
                        pd.to_numeric(frame[col], errors="coerce") == fg_id
                    ]
                    if not matches.empty:
                        return matches

        target = self._normalize_name(full_name)
        for col in ("Name", "PlayerName"):
            if col in frame.columns and target:
                matches = frame[
                    frame[col].astype(str).map(self._normalize_name) == target
                ]
                if not matches.empty:
                    return matches
        return pd.DataFrame()

    def get_history(
        self,
        player_id: int,
        full_name: str,
        start_season: int,
        end_season: int,
        pitcher: bool,
    ) -> list[dict[str, Any]]:
        role = "pitcher_history" if pitcher else "batter_history"
        cached = self.db.get_player_stats(
            player_id, "fangraphs_v5", end_season, role, source_ttl_days(end_season)
        )
        if cached and isinstance(cached.get("rows"), list) and cached["rows"]:
            return cached["rows"]

        frame = pd.DataFrame()
        try:
            direct = self._fetch_api(start_season, end_season, pitcher)
            # A multi-season trend needs a season column. FanGraphs can
            # occasionally return an aggregate row for a range request; do not
            # feed that into a year-by-year chart.
            if direct is not None and not direct.empty and any(
                col in direct.columns for col in ("Season", "season")
            ):
                frame = direct
        except Exception as exc:
            LOGGER.warning("Direct FanGraphs history API failed: %s", exc)

        filtered = self._filter_player_rows(frame, player_id, full_name)

        # If the direct endpoint returned an aggregate/incomplete response,
        # retry through pybaseball's proven season-by-season leaderboard path.
        if filtered.empty:
            try:
                pb = self._pybaseball()
                func = pb.pitching_stats if pitcher else pb.batting_stats
                fallback = func(start_season, end_season, qual=0, ind=1)
                filtered = self._filter_player_rows(
                    fallback, player_id, full_name
                )
            except Exception as exc:
                LOGGER.warning("pybaseball FanGraphs history failed: %s", exc)
                return []

        rows: list[dict[str, Any]] = []
        for _, row in filtered.iterrows():
            raw = row_to_dict(row)
            season_value = first_existing(raw, ("Season", "season"))
            if season_value is None:
                continue
            rows.append(
                {
                    "Season": season_value,
                    "WAR": first_existing(raw, ("WAR",)),
                    "wRC+": first_existing(raw, ("wRC+", "wRC_plus")),
                    "K%": self._pct(first_existing(raw, ("K%", "K_pct"))),
                    "BB%": self._pct(first_existing(raw, ("BB%", "BB_pct"))),
                    "ERA": first_existing(raw, ("ERA",)),
                    "SwStr%": self._pct(
                        first_existing(raw, ("SwStr%", "SwStr_pct"))
                    ),
                }
            )

        # Deduplicate season rows (e.g. traded players) by summing WAR and
        # keeping the latest available rate values. This avoids duplicated x-axis
        # years in the charts.
        by_season: dict[int, dict[str, Any]] = {}
        for row in rows:
            try:
                year = int(float(row["Season"]))
            except (TypeError, ValueError):
                continue
            if year not in by_season:
                by_season[year] = {**row, "Season": year}
                continue
            current = by_season[year]
            for metric in ("WAR",):
                try:
                    current[metric] = float(current.get(metric) or 0) + float(
                        row.get(metric) or 0
                    )
                except (TypeError, ValueError):
                    pass
            for metric in ("wRC+", "K%", "BB%", "ERA", "SwStr%"):
                if row.get(metric) is not None:
                    current[metric] = row[metric]

        final_rows = [by_season[year] for year in sorted(by_season)]
        if final_rows:
            self.db.set_player_stats(
                player_id, "fangraphs_v5", end_season, role, {"rows": final_rows}
            )
        return final_rows
