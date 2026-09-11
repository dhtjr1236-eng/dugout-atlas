from __future__ import annotations

import importlib
import logging
import threading
import time
import unicodedata
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import pandas as pd
from bs4 import BeautifulSoup, Comment

from database.sqlite_manager import SQLiteManager
from services.base_http import HttpError, sync_get_text
from services.bref_local_store import BREF_DATA_PAGE, BRefLocalStore
from services.dataframe_utils import first_existing, row_to_dict
from services.freshness import source_ttl_days

LOGGER = logging.getLogger(__name__)

BREF_BAT_WAR_URL = "https://www.baseball-reference.com/data/war_daily_bat.txt"
BREF_PITCH_WAR_URL = "https://www.baseball-reference.com/data/war_daily_pitch.txt"
BREF_PLAYER_URL = "https://www.baseball-reference.com/players/{letter}/{bbref_id}.shtml"
BREF_SEARCH_URL = "https://www.baseball-reference.com/search/search.fcgi?search={query}"
CACHE_SOURCE = "baseball_reference_v8"


class BaseballReferenceService:
    """Baseball-Reference adapter with a 403-safe local snapshot path.

    Baseball-Reference publishes daily WAR download files, but Sports Reference
    can reject non-browser traffic with HTTP 403/429. The desktop application
    therefore follows these rules:

    1. A user-imported official B-Ref WAR snapshot is always preferred.
    2. If no local snapshot exists, one polite network attempt is allowed.
    3. A 403/429 trips a process-wide circuit breaker, preventing pybaseball or
       player-page retries from hammering the same blocked domain.
    4. bWAR is never substituted with fWAR or a home-grown approximation.
    """

    _daily_cache_lock = threading.Lock()
    _daily_cache: dict[bool, tuple[float, pd.DataFrame]] = {}
    _daily_cache_seconds = 30 * 60

    _request_lock = threading.Lock()
    _last_request_at = 0.0
    _min_request_interval_seconds = 3.25

    _network_state_lock = threading.Lock()
    _network_blocked_until = 0.0
    _network_block_reason = ""
    _network_block_seconds = 24 * 60 * 60

    def __init__(self, db: SQLiteManager) -> None:
        self.db = db
        self.local_store = BRefLocalStore()
        self._fetch_errors: list[str] = []
        self._daily_source: dict[bool, dict[str, str]] = {}

    @staticmethod
    def _pybaseball() -> Any:
        try:
            return importlib.import_module("pybaseball")
        except ImportError as exc:
            raise RuntimeError(
                "pybaseball is not installed. Run install.bat or "
                "pip install -r requirements.txt"
            ) from exc

    @staticmethod
    def _normalize_name(value: str) -> str:
        folded = unicodedata.normalize("NFKD", value)
        asciiish = "".join(ch for ch in folded if not unicodedata.combining(ch))
        return "".join(ch.casefold() for ch in asciiish if ch.isalnum())

    @staticmethod
    def _flatten_columns(frame: pd.DataFrame) -> pd.DataFrame:
        frame = frame.copy()
        if isinstance(frame.columns, pd.MultiIndex):
            cols: list[str] = []
            for parts in frame.columns.to_flat_index():
                meaningful = [
                    str(part).strip()
                    for part in parts
                    if str(part).strip() and not str(part).startswith("Unnamed")
                ]
                cols.append(meaningful[-1] if meaningful else str(parts[-1]))
            frame.columns = cols
        else:
            frame.columns = [str(col).strip() for col in frame.columns]
        return frame

    @classmethod
    def _network_blocked(cls) -> bool:
        with cls._network_state_lock:
            if cls._network_blocked_until <= time.monotonic():
                cls._network_blocked_until = 0.0
                cls._network_block_reason = ""
                return False
            return True

    @classmethod
    def _network_reason(cls) -> str:
        with cls._network_state_lock:
            return cls._network_block_reason

    @classmethod
    def _trip_network_breaker(cls, reason: str) -> None:
        with cls._network_state_lock:
            cls._network_blocked_until = time.monotonic() + cls._network_block_seconds
            cls._network_block_reason = reason

    @classmethod
    def reset_network_breaker(cls) -> None:
        """Used by diagnostics/tests after the user's IP/network state changes."""
        with cls._network_state_lock:
            cls._network_blocked_until = 0.0
            cls._network_block_reason = ""

    @classmethod
    def _wait_for_rate_limit(cls) -> None:
        with cls._request_lock:
            now = time.monotonic()
            wait = cls._min_request_interval_seconds - (now - cls._last_request_at)
            if cls._last_request_at and wait > 0:
                time.sleep(wait)
            cls._last_request_at = time.monotonic()

    def _bref_get_text(self, url: str) -> str:
        if self._network_blocked():
            reason = self._network_reason() or "Baseball-Reference network access is disabled."
            raise HttpError(reason)

        self._wait_for_rate_limit()
        try:
            return sync_get_text(url, retries=1)
        except Exception as exc:
            raw = str(exc)
            if "429" in raw:
                message = (
                    "Baseball-Reference rate limited automated access (HTTP 429). "
                    "Network B-Ref requests are disabled for this app session."
                )
                self._trip_network_breaker(message)
            elif "403" in raw:
                message = (
                    "Baseball-Reference rejected automated access (HTTP 403). "
                    "Download the official WAR file in a normal browser and use "
                    "'B-Ref 파일 가져오기' in MLB Advanced Gameday."
                )
                self._trip_network_breaker(message)
            else:
                message = raw
            self._fetch_errors.append(message)
            raise HttpError(message) from exc

    @staticmethod
    def _tables_from_html(html: str) -> list[pd.DataFrame]:
        soup = BeautifulSoup(html, "lxml")
        for node in soup.find_all(string=lambda text: isinstance(text, Comment)):
            text = str(node)
            if "<table" in text.lower():
                fragment = BeautifulSoup(text, "lxml")
                node.replace_with(fragment)

        try:
            frames = pd.read_html(StringIO(str(soup)))
        except ValueError:
            return []
        return [BaseballReferenceService._flatten_columns(frame) for frame in frames]

    def _html_tables(self, url: str) -> list[pd.DataFrame]:
        return self._tables_from_html(self._bref_get_text(url))

    def import_local_file(self, source: Path | str) -> dict[str, object]:
        """Import a B-Ref official WAR ZIP/TXT/CSV and invalidate B-Ref caches."""
        result = self.local_store.import_path(source)
        with self._daily_cache_lock:
            self._daily_cache.clear()
        self._daily_source.clear()
        self.db.delete_player_stats_source(CACHE_SOURCE)
        return result.to_dict()

    def local_snapshot_status(self) -> dict[str, object]:
        meta = self.local_store.metadata()
        return {
            "batting_available": not self.local_store.load(False).empty,
            "pitching_available": not self.local_store.load(True).empty,
            "metadata": meta,
        }

    def _daily_war_frame(self, pitcher: bool) -> pd.DataFrame:
        """Return an official B-Ref WAR table, preferring user-imported data."""
        local = self.local_store.load(pitcher)
        if not local.empty:
            self._daily_source[pitcher] = self.local_store.snapshot_info(pitcher)
            return self._flatten_columns(local)

        now = time.monotonic()
        with self._daily_cache_lock:
            cached = self._daily_cache.get(pitcher)
            if cached and now - cached[0] < self._daily_cache_seconds:
                return cached[1].copy()

        if self._network_blocked():
            reason = self._network_reason()
            if reason and reason not in self._fetch_errors:
                self._fetch_errors.append(reason)
            return pd.DataFrame()

        url = BREF_PITCH_WAR_URL if pitcher else BREF_BAT_WAR_URL
        frame = pd.DataFrame()
        direct_failed = False
        try:
            text = self._bref_get_text(url)
            frame = pd.read_csv(StringIO(text), low_memory=False)
            self._daily_source[pitcher] = {
                "name": "Baseball-Reference Daily WAR Dataset",
                "url": url,
                "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
            }
        except Exception as exc:
            direct_failed = True
            LOGGER.warning("Direct Baseball-Reference daily WAR source failed: %s", exc)

        # pybaseball's bwar_bat/bwar_pitch calls the same B-Ref URL. It is useful
        # for non-HTTP parser/session differences, but must never run after 403/429.
        if frame.empty and direct_failed and not self._network_blocked():
            try:
                pb = self._pybaseball()
                candidate = (
                    pb.bwar_pitch(return_all=True)
                    if pitcher
                    else pb.bwar_bat(return_all=True)
                )
                if candidate is not None:
                    frame = candidate
                    self._daily_source[pitcher] = {
                        "name": "Baseball-Reference Daily WAR Dataset (pybaseball transport)",
                        "url": url,
                        "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
                    }
            except Exception as exc:
                LOGGER.warning("pybaseball B-Ref WAR transport fallback failed: %s", exc)
                self._fetch_errors.append(f"pybaseball B-Ref fallback: {exc}")

        if frame is not None and not frame.empty:
            frame = self._flatten_columns(frame)
            with self._daily_cache_lock:
                self._daily_cache[pitcher] = (time.monotonic(), frame.copy())
            return frame
        return pd.DataFrame()

    def _war_frame(self, pitcher: bool) -> pd.DataFrame:
        return self._daily_war_frame(pitcher)

    def _bbref_id(self, player_id: int) -> str | None:
        try:
            pb = self._pybaseball()
            frame = pb.playerid_reverse_lookup([int(player_id)], key_type="mlbam")
            if frame is None or frame.empty:
                return None
            raw = frame.iloc[0].get("key_bbref")
            if pd.isna(raw):
                return None
            value = str(raw).strip()
            return value or None
        except Exception as exc:
            LOGGER.info("BRef ID lookup unavailable for %s: %s", player_id, exc)
            return None

    def _match_daily_rows(
        self,
        frame: pd.DataFrame,
        player_id: int,
        season: int,
        full_name: str,
    ) -> pd.DataFrame:
        if frame is None or frame.empty:
            return pd.DataFrame()

        year_col = "year_ID" if "year_ID" in frame.columns else "year_id"
        if year_col not in frame.columns:
            return pd.DataFrame()
        season_mask = pd.to_numeric(frame[year_col], errors="coerce") == int(season)

        for mlb_col in ("mlb_ID", "mlb_id", "mlbID"):
            if mlb_col in frame.columns:
                id_mask = pd.to_numeric(frame[mlb_col], errors="coerce") == int(player_id)
                matches = frame[season_mask & id_mask]
                if not matches.empty:
                    return matches.copy()

        if "player_ID" in frame.columns:
            bbref_id = self._bbref_id(player_id)
            if bbref_id:
                bbref_mask = frame["player_ID"].astype(str).str.strip() == bbref_id
                matches = frame[season_mask & bbref_mask]
                if not matches.empty:
                    return matches.copy()

        if full_name and "name_common" in frame.columns:
            target = self._normalize_name(full_name)
            name_mask = frame["name_common"].astype(str).map(self._normalize_name) == target
            matches = frame[season_mask & name_mask]
            if not matches.empty:
                return matches.copy()
        return pd.DataFrame()

    @staticmethod
    def _bbref_id_from_daily_rows(rows: pd.DataFrame) -> str | None:
        if rows is None or rows.empty or "player_ID" not in rows.columns:
            return None
        for raw in rows["player_ID"].tolist():
            if pd.isna(raw):
                continue
            value = str(raw).strip()
            if value and value.lower() != "nan":
                return value
        return None

    @staticmethod
    def _season_total_row(rows: pd.DataFrame, pitcher: bool) -> pd.Series | None:
        if rows is None or rows.empty:
            return None
        if len(rows) == 1:
            return rows.iloc[0]

        for team_col in ("Team", "Tm", "team", "tm", "team_ID"):
            if team_col in rows.columns:
                team_text = rows[team_col].astype(str).str.upper().str.strip()
                aggregate = rows[
                    team_text.str.fullmatch(r"(?:\d+TM|TOT|TOTAL)", na=False)
                ]
                if not aggregate.empty:
                    return aggregate.iloc[0]

        denominator = ("IP", "BF", "G") if pitcher else ("PA", "AB", "G")
        for col in denominator:
            if col in rows.columns:
                values = pd.to_numeric(rows[col], errors="coerce")
                if values.notna().any():
                    return rows.loc[values.idxmax()]
        return rows.iloc[0]

    @staticmethod
    def _daily_plus_value(rows: pd.DataFrame, pitcher: bool) -> Any:
        if rows is None or rows.empty:
            return None
        plus_columns = (
            ("ERA_plus", "ERA+", "era_plus")
            if pitcher
            else ("OPS_plus", "OPS+", "ops_plus")
        )
        existing = next((col for col in plus_columns if col in rows.columns), None)
        if existing is None:
            return None

        if len(rows) == 1:
            return rows.iloc[0].get(existing)

        total = BaseballReferenceService._season_total_row(rows, pitcher)
        if total is None:
            return None
        team_col = next(
            (col for col in ("Team", "Tm", "team", "tm", "team_ID") if col in rows.columns),
            None,
        )
        if team_col is not None:
            team_text = str(total.get(team_col, "")).upper().strip()
            if not (
                team_text in {"TOT", "TOTAL"}
                or (team_text.endswith("TM") and team_text[:-2].isdigit())
            ):
                return None
        return total.get(existing)

    @staticmethod
    def _player_page_url(bbref_id: str) -> str:
        safe_id = str(bbref_id).strip().lower()
        if not safe_id:
            raise ValueError("Empty Baseball-Reference player id")
        return BREF_PLAYER_URL.format(letter=safe_id[0], bbref_id=safe_id)

    def _season_row_from_player_html(
        self, html: str, season: int, pitcher: bool
    ) -> pd.Series | None:
        plus_key = "ERA+" if pitcher else "OPS+"
        for frame in self._tables_from_html(html):
            if "Season" not in frame.columns or "WAR" not in frame.columns:
                continue
            if plus_key not in frame.columns:
                continue
            season_values = pd.to_numeric(frame["Season"], errors="coerce")
            matches = frame[season_values == int(season)]
            if matches.empty:
                continue
            return self._season_total_row(matches, pitcher)
        return None

    def _player_page_row(
        self,
        bbref_id: str,
        season: int,
        pitcher: bool,
    ) -> tuple[pd.Series | None, str]:
        url = self._player_page_url(bbref_id)
        try:
            html = self._bref_get_text(url)
        except Exception:
            return None, url
        return self._season_row_from_player_html(html, season, pitcher), url

    def _search_player_page_row(
        self, full_name: str, season: int, pitcher: bool
    ) -> tuple[pd.Series | None, str]:
        url = BREF_SEARCH_URL.format(query=quote_plus(full_name.strip()))
        try:
            html = self._bref_get_text(url)
        except Exception:
            return None, url
        return self._season_row_from_player_html(html, season, pitcher), url

    @staticmethod
    def _numeric(value: Any, *, integer: bool = False) -> float | int | None:
        if value is None or pd.isna(value):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return int(round(number)) if integer else number

    def get_bwar(
        self,
        player_id: int,
        season: int,
        pitcher: bool,
        full_name: str = "",
    ) -> dict[str, Any]:
        role = "pitcher" if pitcher else "batter"
        cached = self.db.get_player_stats(
            player_id,
            CACHE_SOURCE,
            season,
            role,
            source_ttl_days(season),
        )
        if cached:
            return cached

        self._fetch_errors = []
        plus_key = "ERA+" if pitcher else "OPS+"
        result: dict[str, Any] = {"bWAR": None, "OPS+": None, "ERA+": None}
        sources: list[dict[str, str]] = []

        daily = self._war_frame(pitcher)
        matches = self._match_daily_rows(daily, player_id, season, full_name)
        if not matches.empty:
            if "WAR" in matches.columns:
                war = pd.to_numeric(matches["WAR"], errors="coerce").sum(min_count=1)
                if not pd.isna(war):
                    result["bWAR"] = float(war)
            result[plus_key] = self._daily_plus_value(matches, pitcher)
            source = self._daily_source.get(pitcher)
            if source:
                sources.append(source)

        # A local official snapshot is deliberately sufficient for bWAR. Do not
        # hit B-Ref player pages after a local import; that would reintroduce the
        # exact 403 problem the import path is designed to avoid.
        using_local = bool(self._daily_source.get(pitcher, {}).get("local_file"))
        page_row: pd.Series | None = None
        player_url = ""
        if not using_local and not self._network_blocked():
            bbref_id = self._bbref_id_from_daily_rows(matches)
            if not bbref_id:
                bbref_id = self._bbref_id(player_id)
            if bbref_id:
                page_row, player_url = self._player_page_row(bbref_id, season, pitcher)
            elif full_name:
                page_row, player_url = self._search_player_page_row(full_name, season, pitcher)

        if page_row is not None:
            raw = row_to_dict(page_row)
            page_war = first_existing(raw, ("WAR",))
            page_plus = first_existing(
                raw,
                ("ERA+", "ERA_plus", "era_plus")
                if pitcher
                else ("OPS+", "OPS_plus", "ops_plus"),
            )
            if page_war is not None:
                result["bWAR"] = page_war
            if page_plus is not None:
                result[plus_key] = page_plus
            sources.append(
                {
                    "name": "Baseball-Reference Player Page",
                    "url": player_url,
                    "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
                }
            )

        result["bWAR"] = self._numeric(result.get("bWAR"))
        result["OPS+"] = self._numeric(result.get("OPS+"), integer=True)
        result["ERA+"] = self._numeric(result.get("ERA+"), integer=True)

        available = any(result.get(key) is not None for key in ("bWAR", "OPS+", "ERA+"))
        if available:
            role_plus = result.get(plus_key)
            is_partial = result.get("bWAR") is None or role_plus is None
            result["_status"] = "partial" if is_partial else "ok"
            result["_sources"] = sources
            if self._fetch_errors:
                result["_errors"] = list(dict.fromkeys(self._fetch_errors))
            self.db.set_player_stats(player_id, CACHE_SOURCE, season, role, result)
            return result

        result["_status"] = "unavailable"
        errors = list(dict.fromkeys(self._fetch_errors))
        if not errors:
            if self._network_blocked():
                errors.append(self._network_reason())
            else:
                errors.append(
                    "No Baseball-Reference WAR snapshot matched this player/season. "
                    "Open the official B-Ref data page in a browser, download the latest "
                    "WAR archive, and import it with 'B-Ref 파일 가져오기'."
                )
        result["_errors"] = errors
        result["_sources"] = [
            {
                "name": "Baseball-Reference official WAR downloads",
                "url": BREF_DATA_PAGE,
                "as_of": "",
            }
        ]
        return result
