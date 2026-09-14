from __future__ import annotations

import importlib
import json
import logging
import re
import time
import unicodedata
from calendar import monthrange
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlencode

import pandas as pd
import requests

from config.settings import SETTINGS
from database.sqlite_manager import SQLiteManager
from services.base_http import HttpError
from services.dataframe_utils import first_existing, row_to_dict
from services.freshness import source_ttl_days

LOGGER = logging.getLogger(__name__)
FG_LEADERS_URL = "https://www.fangraphs.com/api/leaders/major-league/data"
FG_GAME_LOG_URL = "https://www.fangraphs.com/api/players/game-log"
FG_USER_AGENT = "okhttp/4.12.0"
FG_CACHE_SOURCE = "fangraphs_v6"
CURRENT_FG_TTL_MINUTES = 5
DAILY_TREND_GAME_LIMIT = 14


class FanGraphsService:
    """FanGraphs JSON adapter with current-season and period trend support.

    The FanGraphs site currently permits the mobile-app HTTP client while generic
    clients can be challenged by Cloudflare. All direct FanGraphs calls therefore
    use the mobile-app User-Agent, and current-season summary/trend data is cached
    for only a few minutes.
    """

    def __init__(self, db: SQLiteManager) -> None:
        self.db = db
        self._fg_id_cache: dict[int, int] = {}

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
    def _cache_ttl_days(season: int) -> float:
        if int(season) == date.today().year:
            return CURRENT_FG_TTL_MINUTES / (24.0 * 60.0)
        return source_ttl_days(season)

    @staticmethod
    def _api_params(
        start: int,
        end: int,
        pitcher: bool,
        *,
        start_date: str = "",
        end_date: str = "",
        ind: int = 1,
    ) -> dict[str, Any]:
        custom_range = bool(start_date or end_date)
        return {
            "age": "",
            "pos": "all",
            "stats": "pit" if pitcher else "bat",
            "lg": "all",
            "qual": "0",
            "season": end,
            "season1": start,
            "startdate": start_date,
            "enddate": end_date,
            "month": "1000" if custom_range else "0",
            "team": "0",
            "pageitems": "10000",
            "pagenum": "1",
            "ind": str(ind),
            "rost": "0",
            "players": "",
            "type": "8",
            "postseason": "",
            "sortdir": "default",
            "sortstat": "WAR",
        }

    @staticmethod
    def _request_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "User-Agent": FG_USER_AGENT,
            "Accept": "application/json",
        }
        last_error: Exception | None = None
        for attempt in range(1, SETTINGS.request_retries + 1):
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=SETTINGS.request_timeout_seconds,
                )
                if response.status_code == 403:
                    raise HttpError(
                        "FanGraphs rejected the mobile-app request (HTTP 403). "
                        "Its Cloudflare access policy may have changed."
                    )
                if response.status_code == 429:
                    raise HttpError("FanGraphs rate limited this client (HTTP 429).")
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise HttpError(f"Expected FanGraphs JSON object from {url}")
                return payload
            except (requests.RequestException, ValueError, HttpError) as exc:
                last_error = exc
                LOGGER.warning(
                    "FanGraphs GET failed attempt %s/%s: %s (%s)",
                    attempt,
                    SETTINGS.request_retries,
                    url,
                    exc,
                )
                if isinstance(exc, HttpError) and ("403" in str(exc) or "429" in str(exc)):
                    break
                if attempt < SETTINGS.request_retries:
                    time.sleep(min(2 ** (attempt - 1), 4))
        raise HttpError(str(last_error or "Unknown FanGraphs HTTP error"))

    def _leaderboard_url(
        self,
        start: int,
        end: int,
        pitcher: bool,
        *,
        start_date: str = "",
        end_date: str = "",
        ind: int = 1,
    ) -> str:
        params = self._api_params(
            start,
            end,
            pitcher,
            start_date=start_date,
            end_date=end_date,
            ind=ind,
        )
        return f"{FG_LEADERS_URL}?{urlencode(params)}"

    def _fetch_api(
        self,
        start: int,
        end: int,
        pitcher: bool,
        *,
        start_date: str = "",
        end_date: str = "",
        ind: int = 1,
    ) -> pd.DataFrame:
        params = self._api_params(
            start,
            end,
            pitcher,
            start_date=start_date,
            end_date=end_date,
            ind=ind,
        )
        payload = self._request_json(FG_LEADERS_URL, params)
        rows = payload.get("data", [])
        return pd.DataFrame(rows if isinstance(rows, list) else [])

    def _fangraphs_id(self, player_id: int) -> int | None:
        """Best-effort Chadwick lookup used only after direct MLBAM matching."""
        cached = self._fg_id_cache.get(int(player_id))
        if cached is not None:
            return cached
        try:
            pb = self._pybaseball()
            frame = pb.playerid_reverse_lookup([int(player_id)], key_type="mlbam")
            if frame is None or frame.empty:
                return None
            raw = frame.iloc[0].get("key_fangraphs")
            value = int(raw) if pd.notna(raw) else None
            if value is not None:
                self._fg_id_cache[int(player_id)] = value
            return value
        except Exception as exc:
            LOGGER.info("FanGraphs ID lookup unavailable for %s: %s", player_id, exc)
            return None

    def _remember_fangraphs_id(self, player_id: int, raw: dict[str, Any]) -> None:
        for key in ("playerid", "IDfg", "PlayerId"):
            value = raw.get(key)
            try:
                if value is not None and str(value).strip():
                    self._fg_id_cache[int(player_id)] = int(float(value))
                    return
            except (TypeError, ValueError):
                continue

    def _find_player_row(
        self, frame: pd.DataFrame, player_id: int, full_name: str
    ) -> pd.Series | None:
        if frame is None or frame.empty:
            return None

        for col in ("xMLBAMID", "MLBAMID", "mlbam_id", "key_mlbam"):
            if col in frame.columns:
                matches = frame[pd.to_numeric(frame[col], errors="coerce") == int(player_id)]
                if not matches.empty:
                    return matches.iloc[0]

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
                    matches = frame[pd.to_numeric(frame[col], errors="coerce") == fg_id]
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

    @staticmethod
    def _has_metrics(result: dict[str, Any]) -> bool:
        return any(
            value is not None
            for key, value in result.items()
            if not key.startswith("_")
        )

    def get_batter(self, player_id: int, full_name: str, season: int) -> dict[str, Any]:
        cached = self.db.get_player_stats(
            player_id,
            FG_CACHE_SOURCE,
            season,
            "batter",
            self._cache_ttl_days(season),
        )
        if cached:
            return cached
        frame = self._season_frame(season, False)
        row = self._find_player_row(frame, player_id, full_name)
        if row is None:
            return {}
        raw = row_to_dict(row)
        self._remember_fangraphs_id(player_id, raw)
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
            "_status": "ok",
            "_source": {
                "name": "FanGraphs Major League Leaderboards",
                "url": self._leaderboard_url(season, season, False),
                "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
            },
        }
        if self._has_metrics(result):
            self.db.set_player_stats(player_id, FG_CACHE_SOURCE, season, "batter", result)
        return result

    def get_pitcher(self, player_id: int, full_name: str, season: int) -> dict[str, Any]:
        cached = self.db.get_player_stats(
            player_id,
            FG_CACHE_SOURCE,
            season,
            "pitcher",
            self._cache_ttl_days(season),
        )
        if cached:
            return cached
        frame = self._season_frame(season, True)
        row = self._find_player_row(frame, player_id, full_name)
        if row is None:
            return {}
        raw = row_to_dict(row)
        self._remember_fangraphs_id(player_id, raw)
        result = {
            "fWAR": first_existing(raw, ("WAR",)),
            "ERA": first_existing(raw, ("ERA",)),
            "FIP": first_existing(raw, ("FIP",)),
            "xFIP": first_existing(raw, ("xFIP",)),
            "WHIP": first_existing(raw, ("WHIP",)),
            "K%": self._pct(first_existing(raw, ("K%", "K_pct"))),
            "BB%": self._pct(first_existing(raw, ("BB%", "BB_pct"))),
            "_status": "ok",
            "_source": {
                "name": "FanGraphs Major League Leaderboards",
                "url": self._leaderboard_url(season, season, True),
                "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
            },
        }
        if self._has_metrics(result):
            self.db.set_player_stats(player_id, FG_CACHE_SOURCE, season, "pitcher", result)
        return result

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
            player_id,
            FG_CACHE_SOURCE,
            end_season,
            role,
            self._cache_ttl_days(end_season),
        )
        if cached and isinstance(cached.get("rows"), list) and cached["rows"]:
            return cached["rows"]

        frame = pd.DataFrame()
        try:
            direct = self._fetch_api(start_season, end_season, pitcher)
            if direct is not None and not direct.empty and any(
                col in direct.columns for col in ("Season", "season")
            ):
                frame = direct
        except Exception as exc:
            LOGGER.warning("Direct FanGraphs history API failed: %s", exc)

        filtered = self._filter_player_rows(frame, player_id, full_name)
        if filtered.empty:
            try:
                pb = self._pybaseball()
                func = pb.pitching_stats if pitcher else pb.batting_stats
                fallback = func(start_season, end_season, qual=0, ind=1)
                filtered = self._filter_player_rows(fallback, player_id, full_name)
            except Exception as exc:
                LOGGER.warning("pybaseball FanGraphs history failed: %s", exc)
                return []

        rows: list[dict[str, Any]] = []
        for _, row in filtered.iterrows():
            raw = row_to_dict(row)
            self._remember_fangraphs_id(player_id, raw)
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
            try:
                current["WAR"] = float(current.get("WAR") or 0) + float(
                    row.get("WAR") or 0
                )
            except (TypeError, ValueError):
                pass
            for metric in ("wRC+", "K%", "BB%", "ERA", "SwStr%"):
                if row.get(metric) is not None:
                    current[metric] = row[metric]

        final_rows = [by_season[year] for year in sorted(by_season)]
        if final_rows:
            self.db.set_player_stats(
                player_id,
                FG_CACHE_SOURCE,
                end_season,
                role,
                {"rows": final_rows},
            )
        return final_rows

    def _resolve_fangraphs_id(
        self, player_id: int, full_name: str, season: int, pitcher: bool
    ) -> int | None:
        cached = self._fg_id_cache.get(int(player_id))
        if cached is not None:
            return cached
        try:
            frame = self._fetch_api(season, season, pitcher)
            row = self._find_player_row(frame, player_id, full_name)
            if row is not None:
                raw = row_to_dict(row)
                self._remember_fangraphs_id(player_id, raw)
                cached = self._fg_id_cache.get(int(player_id))
                if cached is not None:
                    return cached
        except Exception as exc:
            LOGGER.info("Could not resolve FanGraphs ID directly: %s", exc)
        return self._fangraphs_id(player_id)

    def _game_log_frame(
        self, player_id: int, full_name: str, season: int, pitcher: bool
    ) -> pd.DataFrame:
        fg_id = self._resolve_fangraphs_id(player_id, full_name, season, pitcher)
        if fg_id is None:
            return pd.DataFrame()
        params = {
            "playerid": str(fg_id),
            "position": "P" if pitcher else "",
            "type": "0",
            "gds": "",
            "gde": "",
            "season": str(season),
        }
        payload = self._request_json(FG_GAME_LOG_URL, params)
        rows = payload.get("mlb", [])
        return pd.DataFrame(rows if isinstance(rows, list) else [])

    @staticmethod
    def _extract_date(value: Any) -> date | None:
        text = re.sub(r"<[^>]+>", "", str(value or "")).strip()
        if not text:
            return None
        match = re.search(r"\d{4}-\d{2}-\d{2}", text)
        if match:
            try:
                return date.fromisoformat(match.group(0))
            except ValueError:
                return None
        try:
            parsed = pd.to_datetime(text, errors="raise")
            return parsed.date()
        except Exception:
            return None

    def _game_dates(
        self, player_id: int, full_name: str, season: int, pitcher: bool
    ) -> list[date]:
        frame = self._game_log_frame(player_id, full_name, season, pitcher)
        if frame.empty:
            return []
        date_col = next(
            (col for col in ("Date", "gamedate", "GameDate", "game_date") if col in frame.columns),
            None,
        )
        if date_col is None:
            return []
        values = {
            parsed
            for parsed in (self._extract_date(value) for value in frame[date_col].tolist())
            if parsed is not None and parsed.year == int(season)
        }
        return sorted(values)

    def _range_row(
        self,
        player_id: int,
        full_name: str,
        season: int,
        pitcher: bool,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any] | None:
        frame = self._fetch_api(
            season,
            season,
            pitcher,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            ind=0,
        )
        row = self._find_player_row(frame, player_id, full_name)
        if row is None:
            return None
        raw = row_to_dict(row)
        self._remember_fangraphs_id(player_id, raw)
        return {
            "WAR": first_existing(raw, ("WAR",)),
            "wRC+": first_existing(raw, ("wRC+", "wRC_plus")),
        }

    def _monthly_history(
        self, player_id: int, full_name: str, season: int, pitcher: bool
    ) -> list[dict[str, Any]]:
        today = date.today()
        end_limit = today if int(season) == today.year else date(int(season), 10, 31)
        first = date(int(season), 3, 1)
        if end_limit < first:
            return []

        rows: list[dict[str, Any]] = []
        cursor = first
        while cursor <= end_limit:
            last_day = monthrange(cursor.year, cursor.month)[1]
            month_end = min(date(cursor.year, cursor.month, last_day), end_limit)
            try:
                metrics = self._range_row(
                    player_id,
                    full_name,
                    season,
                    pitcher,
                    cursor,
                    month_end,
                )
            except Exception as exc:
                LOGGER.warning("FanGraphs monthly trend failed for %s: %s", cursor, exc)
                metrics = None
            if metrics and any(value is not None for value in metrics.values()):
                rows.append({"Period": cursor.strftime("%Y-%m"), **metrics})
            if cursor.month == 12:
                cursor = date(cursor.year + 1, 1, 1)
            else:
                cursor = date(cursor.year, cursor.month + 1, 1)
        return rows

    def _daily_history(
        self, player_id: int, full_name: str, season: int, pitcher: bool
    ) -> list[dict[str, Any]]:
        dates = self._game_dates(player_id, full_name, season, pitcher)
        dates = dates[-DAILY_TREND_GAME_LIMIT:]
        rows: list[dict[str, Any]] = []
        for game_date in dates:
            try:
                metrics = self._range_row(
                    player_id,
                    full_name,
                    season,
                    pitcher,
                    game_date,
                    game_date,
                )
            except Exception as exc:
                LOGGER.warning("FanGraphs daily trend failed for %s: %s", game_date, exc)
                metrics = None
            if metrics and any(value is not None for value in metrics.values()):
                rows.append({"Period": game_date.isoformat(), **metrics})
        return rows

    def get_period_history(
        self,
        player_id: int,
        full_name: str,
        season: int,
        pitcher: bool,
        period: str,
    ) -> list[dict[str, Any]]:
        """Return FanGraphs WAR/wRC+ grouped by year, month, or recent game-day.

        Daily mode is intentionally bounded to the most recent 14 games because
        FanGraphs exposes exact daily WAR through date-range leaderboard queries,
        not in its normal game-log payload. The bounded window avoids turning one
        chart click into a full-season crawl.
        """
        normalized = period.strip().lower()
        if normalized == "yearly":
            rows = self.get_history(
                player_id,
                full_name,
                max(2002, int(season) - 5),
                int(season),
                pitcher,
            )
            return [
                {"Period": str(row.get("Season")), **row}
                for row in rows
                if row.get("Season") is not None
            ]
        if normalized not in {"monthly", "daily"}:
            raise ValueError(f"Unsupported FanGraphs trend period: {period}")

        role = f"{'pitcher' if pitcher else 'batter'}_trend_{normalized}"
        cached = self.db.get_player_stats(
            player_id,
            FG_CACHE_SOURCE,
            int(season),
            role,
            self._cache_ttl_days(int(season)),
        )
        if cached and isinstance(cached.get("rows"), list) and cached["rows"]:
            return cached["rows"]

        if normalized == "monthly":
            rows = self._monthly_history(player_id, full_name, season, pitcher)
        else:
            rows = self._daily_history(player_id, full_name, season, pitcher)

        if rows:
            self.db.set_player_stats(
                player_id,
                FG_CACHE_SOURCE,
                int(season),
                role,
                {"rows": rows},
            )
        return rows
