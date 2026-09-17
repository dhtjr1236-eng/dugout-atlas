from __future__ import annotations

import asyncio
import logging
import math
import time
import unicodedata
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlencode

LOGGER = logging.getLogger(__name__)
PLATOON_CACHE_SOURCE = "fangraphs_platoon_v1"
FANGRAPHS_SPLIT_MONTHS = {"left": "13", "right": "14"}
MLB_SPLIT_CODES = {"left": "vl", "right": "vr"}
_ROSTER_CACHE: dict[int, list[dict[str, Any]]] = {}


def _normalize_search_text(value: Any) -> str:
    folded = unicodedata.normalize("NFKD", str(value or ""))
    asciiish = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return " ".join("".join(ch.casefold() if ch.isalnum() else " " for ch in asciiish).split())


def _canonical_key(value: Any) -> str:
    return "".join(ch for ch in _normalize_search_text(value) if ch.isalnum())


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip().replace(",", "")
        if not value or value in {"—", "-", "--", "---", "- - -"}:
            return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _extract_metrics(raw: dict[str, Any]) -> dict[str, float | None]:
    aliases = {
        "AVG": ("AVG", "avg", "batting_average"),
        "OBP": ("OBP", "obp", "on_base_percentage"),
        "SLG": ("SLG", "slg", "slugging_percentage"),
        "OPS": ("OPS", "ops", "on_base_plus_slugging"),
        "wRC+": ("wRC+", "wRC_plus", "wrc_plus", "wrcplus"),
    }
    canonical = {_canonical_key(key): value for key, value in raw.items()}
    result: dict[str, float | None] = {}
    for metric, names in aliases.items():
        value = None
        for name in names:
            key = _canonical_key(name)
            if key in canonical:
                value = _safe_float(canonical[key])
                if value is not None:
                    break
        result[metric] = value
    if result["OPS"] is None and result["OBP"] is not None and result["SLG"] is not None:
        result["OPS"] = float(result["OBP"] + result["SLG"])
    return result


def _merge_missing(primary: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    merged = dict(primary)
    for key in ("AVG", "OBP", "SLG", "OPS", "wRC+"):
        if merged.get(key) is None and fallback.get(key) is not None:
            merged[key] = fallback[key]
    if merged.get("OPS") is None and merged.get("OBP") is not None and merged.get("SLG") is not None:
        merged["OPS"] = float(merged["OBP"] + merged["SLG"])
    return merged


def _choose_default_season(seasons: list[int], current_year: int | None = None) -> int:
    year = int(current_year or date.today().year)
    valid = sorted({int(item) for item in seasons if int(item) > 0}, reverse=True)
    if year in valid:
        return year
    return valid[0] if valid else year


def _format_rate(value: Any, *, wrc: bool = False) -> str:
    number = _safe_float(value)
    if number is None:
        return "—"
    if wrc:
        return f"{number:.0f}" if abs(number - round(number)) < 0.05 else f"{number:.1f}"
    return f"{number:.3f}"


def _extract_years(payload: dict[str, Any]) -> set[int]:
    years: set[int] = set()
    for bucket in payload.get("stats", []) or []:
        for split in bucket.get("splits", []) or []:
            raw = split.get("season")
            try:
                years.add(int(raw))
            except (TypeError, ValueError):
                continue
    return years


async def _available_player_seasons(player_id: int) -> list[int]:
    from config.settings import SETTINGS
    from services.base_http import async_get_json

    base = SETTINGS.mlb_api_base.rstrip("/")

    async def fetch(group: str) -> dict[str, Any]:
        return await async_get_json(
            f"{base}/v1/people/{int(player_id)}/stats",
            params={"stats": "yearByYear", "group": group, "gameType": "R"},
        )

    responses = await asyncio.gather(fetch("hitting"), fetch("pitching"), return_exceptions=True)
    years: set[int] = set()
    for response in responses:
        if isinstance(response, Exception):
            LOGGER.info("선수 시즌 목록 조회 일부 실패 player_id=%s: %s", player_id, response)
            continue
        years.update(_extract_years(response))
    if not years:
        years.add(date.today().year)
    return sorted(years, reverse=True)


async def _current_roster_search(query: str) -> list[dict[str, Any]]:
    from config.settings import SETTINGS
    from services.base_http import async_get_json

    season = date.today().year
    rows = _ROSTER_CACHE.get(season)
    if rows is None:
        payload = await async_get_json(
            f"{SETTINGS.mlb_api_base.rstrip('/')}/v1/sports/1/players",
            params={"season": season, "gameType": "R"},
        )
        parsed: list[dict[str, Any]] = []
        for person in payload.get("people", []) or []:
            try:
                player_id = int(person.get("id", 0) or 0)
            except (TypeError, ValueError):
                continue
            if not player_id:
                continue
            position = person.get("primaryPosition", {}) or {}
            parsed.append(
                {
                    "id": player_id,
                    "name": str(person.get("fullName", "")),
                    "first_name": str(person.get("firstName", "")),
                    "last_name": str(person.get("lastName", "")),
                    "position": str(position.get("abbreviation", "")),
                    "team": "",
                }
            )
        rows = parsed
        _ROSTER_CACHE[season] = rows

    needle = _normalize_search_text(query)
    compact = needle.replace(" ", "")
    matches: list[dict[str, Any]] = []
    for row in rows:
        values = (
            row.get("name", ""),
            row.get("first_name", ""),
            row.get("last_name", ""),
        )
        normalized = [_normalize_search_text(value) for value in values]
        if any(needle and needle in value for value in normalized) or any(
            compact and compact in value.replace(" ", "") for value in normalized
        ):
            matches.append(row)
    return matches


def _search_score(name: str, query: str) -> tuple[int, int, str]:
    normalized_name = _normalize_search_text(name)
    normalized_query = _normalize_search_text(query)
    tokens = normalized_name.split()
    if normalized_name == normalized_query:
        bucket = 0
    elif normalized_query in tokens:
        bucket = 1
    elif any(token.startswith(normalized_query) for token in tokens):
        bucket = 2
    elif normalized_query in normalized_name:
        bucket = 3
    else:
        bucket = 4
    return bucket, len(normalized_name), normalized_name


def _dedupe_and_rank(rows: list[dict[str, Any]], query: str, limit: int = 10) -> list[dict[str, Any]]:
    unique: dict[int, dict[str, Any]] = {}
    for row in rows:
        try:
            player_id = int(row.get("id", 0) or 0)
        except (TypeError, ValueError):
            continue
        if player_id and player_id not in unique:
            unique[player_id] = row
    ranked = sorted(unique.values(), key=lambda row: _search_score(str(row.get("name", "")), query))
    return ranked[:limit]


def _fetch_fangraphs_split(
    service: Any,
    player_id: int,
    full_name: str,
    season: int,
    pitcher: bool,
    month: str,
) -> tuple[dict[str, Any], str]:
    import pandas as pd

    from services.dataframe_utils import row_to_dict
    from services.fangraphs_service import FG_LEADERS_URL

    params = service._api_params(int(season), int(season), bool(pitcher))
    params["month"] = str(month)
    payload = service._request_json(FG_LEADERS_URL, params)
    rows = payload.get("data", [])
    frame = pd.DataFrame(rows if isinstance(rows, list) else [])
    row = service._find_player_row(frame, int(player_id), full_name)
    if row is None:
        return {}, f"{FG_LEADERS_URL}?{urlencode(params)}"
    raw = row_to_dict(row)
    return _extract_metrics(raw), f"{FG_LEADERS_URL}?{urlencode(params)}"


def _fetch_mlb_split(
    player_id: int,
    season: int,
    pitcher: bool,
    sit_code: str,
) -> tuple[dict[str, Any], str]:
    import requests

    from config.settings import SETTINGS

    group = "pitching" if pitcher else "hitting"
    url = f"{SETTINGS.mlb_api_base.rstrip('/')}/v1/people/{int(player_id)}/stats"
    params = {
        "stats": "statSplits",
        "group": group,
        "gameType": "R",
        "sitCodes": sit_code,
        "season": int(season),
    }
    session = requests.Session()
    session.headers.update({"User-Agent": SETTINGS.user_agent, "Accept": "application/json"})
    last_error: Exception | None = None
    for attempt in range(1, SETTINGS.request_retries + 1):
        try:
            response = session.get(url, params=params, timeout=SETTINGS.request_timeout_seconds)
            response.raise_for_status()
            payload = response.json()
            for bucket in payload.get("stats", []) or []:
                splits = bucket.get("splits", []) or []
                if not splits:
                    continue
                stat = splits[0].get("stat", {}) or {}
                metrics = _extract_metrics(stat)
                return metrics, str(response.url)
            return {}, str(response.url)
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < SETTINGS.request_retries:
                time.sleep(min(1.5 * attempt, 4.5))
    raise RuntimeError(f"MLB platoon split request failed: {last_error}")


def get_platoon_splits(
    service: Any,
    player_id: int,
    full_name: str,
    season: int,
    pitcher: bool,
) -> dict[str, Any]:
    role = "pitcher" if pitcher else "batter"
    cached = service.db.get_player_stats(
        int(player_id),
        PLATOON_CACHE_SOURCE,
        int(season),
        role,
        service._cache_ttl_days(int(season)),
    )
    if cached:
        return cached

    labels = (
        {"left": "vs LHB", "right": "vs RHB"}
        if pitcher
        else {"left": "vs LHP", "right": "vs RHP"}
    )
    result: dict[str, Any] = {}
    sources: list[dict[str, str]] = []
    errors: list[str] = []

    for side in ("left", "right"):
        fg_metrics: dict[str, Any] = {}
        fg_url = ""
        try:
            fg_metrics, fg_url = _fetch_fangraphs_split(
                service,
                int(player_id),
                full_name,
                int(season),
                bool(pitcher),
                FANGRAPHS_SPLIT_MONTHS[side],
            )
        except Exception as exc:
            errors.append(f"FanGraphs {labels[side]}: {exc}")
            LOGGER.info("FanGraphs platoon split failed player=%s season=%s side=%s: %s", player_id, season, side, exc)

        mlb_metrics: dict[str, Any] = {}
        mlb_url = ""
        if not all(fg_metrics.get(key) is not None for key in ("AVG", "OBP", "SLG", "OPS")):
            try:
                mlb_metrics, mlb_url = _fetch_mlb_split(
                    int(player_id), int(season), bool(pitcher), MLB_SPLIT_CODES[side]
                )
            except Exception as exc:
                errors.append(f"MLB {labels[side]}: {exc}")
                LOGGER.info("MLB platoon split failed player=%s season=%s side=%s: %s", player_id, season, side, exc)

        merged = _merge_missing(fg_metrics, mlb_metrics)
        merged["label"] = labels[side]
        result[side] = merged
        if fg_url:
            sources.append(
                {
                    "name": f"FanGraphs Platoon Split — {labels[side]}",
                    "url": fg_url,
                    "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
                }
            )
        if mlb_url:
            sources.append(
                {
                    "name": f"MLB Stats API Platoon Split — {labels[side]}",
                    "url": mlb_url,
                    "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
                }
            )

    has_left = any(result.get("left", {}).get(key) is not None for key in ("AVG", "OBP", "SLG", "OPS", "wRC+"))
    has_right = any(result.get("right", {}).get(key) is not None for key in ("AVG", "OBP", "SLG", "OPS", "wRC+"))
    result["_status"] = "ok" if has_left and has_right else "partial" if has_left or has_right else "unavailable"
    result["_sources"] = sources
    if errors:
        result["_errors"] = errors
    if has_left or has_right:
        service.db.set_player_stats(int(player_id), PLATOON_CACHE_SOURCE, int(season), role, result)
    return result


def install_player_enhancements() -> None:
    """검색 보강, 선수 시즌 선택, 좌우 플래툰 스플릿 UI를 기존 화면에 최소 패치로 추가한다."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QComboBox,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    from controllers.app_controller import AppController
    from services.player_service import PlayerService
    from ui.compare_view import CompareView
    from ui.main_window import MainWindow
    from ui.player_view import PlayerView

    if getattr(PlayerService, "_player_enhancements_installed", False):
        return

    original_search = PlayerService.search
    original_get_bundle = PlayerService.get_bundle
    original_main_init = MainWindow.__init__
    original_compare_init = CompareView.__init__
    original_player_init = PlayerView.__init__
    original_show_batter = PlayerView._show_batter
    original_show_pitcher = PlayerView._show_pitcher
    original_controller_init = AppController.__init__
    original_load_trend = AppController.load_player_trend
    original_load_pitcher_period = AppController.load_pitcher_statcast_period

    async def search_with_contains_fallback(self: PlayerService, query: str) -> list[dict[str, Any]]:
        rows = await original_search(self, query)
        normalized = _normalize_search_text(query)
        direct_has_match = any(
            normalized and normalized in _normalize_search_text(row.get("name", ""))
            for row in rows
        )
        if not direct_has_match:
            try:
                rows = list(rows) + await _current_roster_search(query)
            except Exception as exc:
                LOGGER.info("MLB 전체 선수 검색 폴백 실패 query=%r: %s", query, exc)
        return _dedupe_and_rank(list(rows), query)

    async def get_bundle_with_platoon(
        self: PlayerService, player_id: int, season: int
    ):
        bundle = await original_get_bundle(self, player_id, season)
        try:
            platoon = await asyncio.to_thread(
                get_platoon_splits,
                self.fangraphs,
                player_id,
                bundle.profile.full_name,
                season,
                bundle.profile.is_pitcher,
            )
            bundle.fangraphs["_platoon"] = platoon
            existing_sources = bundle.fangraphs.setdefault("_sources", [])
            if isinstance(existing_sources, list):
                for source in platoon.get("_sources", []) if isinstance(platoon, dict) else []:
                    if not isinstance(source, dict):
                        continue
                    if not any(
                        isinstance(item, dict) and item.get("url") == source.get("url")
                        for item in existing_sources
                    ):
                        existing_sources.append(source)
            for message in platoon.get("_errors", []) if isinstance(platoon, dict) else []:
                if message:
                    bundle.errors.append(f"Platoon: {message}")
        except Exception as exc:
            LOGGER.exception("Platoon split failed player=%s season=%s", player_id, season)
            bundle.errors.append(f"Platoon: {exc}")
        return bundle

    def main_search_enter_contains(self: MainWindow) -> None:
        text = _normalize_search_text(self.search.text())
        candidates: list[tuple[tuple[int, int, str], int]] = []
        for label, player_id in self._search_map.items():
            name = label.split(" — ", 1)[0]
            normalized_name = _normalize_search_text(name)
            if text and text in normalized_name:
                candidates.append((_search_score(name, text), player_id))
        if candidates:
            candidates.sort(key=lambda item: item[0])
            self.search_player_selected.emit(candidates[0][1])

    def init_main_with_contains(self: MainWindow) -> None:
        original_main_init(self)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)

    def compare_search_enter_contains(self: CompareView, slot: int) -> None:
        text = _normalize_search_text(self.current_query(slot))
        candidates: list[tuple[tuple[int, int, str], int]] = []
        for label, player_id in self._search_maps.get(slot, {}).items():
            name = label.split(" — ", 1)[0]
            normalized_name = _normalize_search_text(name)
            if text and text in normalized_name:
                candidates.append((_search_score(name, text), player_id))
        if candidates:
            candidates.sort(key=lambda item: item[0])
            self.player_selected.emit(slot, candidates[0][1])

    def init_compare_with_contains(self: CompareView) -> None:
        original_compare_init(self)
        for completer in self._completers.values():
            completer.setFilterMode(Qt.MatchFlag.MatchContains)

    def handle_player_season_change(self: PlayerView) -> None:
        if self.player_season_combo.signalsBlocked():
            return
        raw = self.player_season_combo.currentData()
        try:
            selected = int(raw)
        except (TypeError, ValueError):
            return
        callback = getattr(self, "_season_change_callback", None)
        if callable(callback):
            callback(selected)

    def set_available_seasons(self: PlayerView, seasons: list[int], selected: int) -> None:
        values = sorted({int(item) for item in seasons if int(item) > 0}, reverse=True)
        if selected not in values:
            values.insert(0, int(selected))
        self.player_season_combo.blockSignals(True)
        self.player_season_combo.clear()
        for year in values:
            self.player_season_combo.addItem(str(year), year)
        index = self.player_season_combo.findData(int(selected))
        self.player_season_combo.setCurrentIndex(max(index, 0))
        self.player_season_combo.setEnabled(bool(values))
        self.player_season_combo.blockSignals(False)

    def fill_platoon_table(self: PlayerView, bundle: Any, pitcher: bool) -> None:
        platoon = bundle.fangraphs.get("_platoon", {}) if isinstance(bundle.fangraphs, dict) else {}
        rows = [platoon.get("left", {}), platoon.get("right", {})] if isinstance(platoon, dict) else [{}, {}]
        default_labels = ("vs LHB", "vs RHB") if pitcher else ("vs LHP", "vs RHP")
        for row_index, split in enumerate(rows):
            split = split if isinstance(split, dict) else {}
            label = str(split.get("label") or default_labels[row_index])
            values = [
                label,
                _format_rate(split.get("AVG")),
                _format_rate(split.get("OBP")),
                _format_rate(split.get("SLG")),
                _format_rate(split.get("OPS")),
                _format_rate(split.get("wRC+"), wrc=True),
            ]
            for col, value in enumerate(values):
                self.platoon_table.setItem(row_index, col, QTableWidgetItem(value))
        if pitcher and all(
            not isinstance(split, dict) or split.get("wRC+") is None for split in rows
        ):
            self.platoon_note.setText(
                "투수 상대 wRC+는 FanGraphs split 응답에 값이 제공되는 경우에만 표시됩니다."
            )
        else:
            self.platoon_note.setText(
                "좌/우 상대 성적은 FanGraphs split을 우선 사용하고, 누락된 slash line은 MLB Stats API로 보완합니다."
            )

    def init_player_with_season_and_platoon(self: PlayerView) -> None:
        original_player_init(self)

        name_index = self.layout.indexOf(self.name_label)
        self.layout.removeWidget(self.name_label)
        self.player_name_row = QWidget(self.content)
        name_layout = QHBoxLayout(self.player_name_row)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.addWidget(self.name_label)
        name_layout.addStretch()
        name_layout.addWidget(QLabel("시즌"))
        self.player_season_combo = QComboBox()
        self.player_season_combo.setMinimumWidth(92)
        self.player_season_combo.setEnabled(False)
        self.player_season_combo.setToolTip("선택한 시즌 기준으로 선수 페이지 전체 데이터를 다시 불러옵니다.")
        name_layout.addWidget(self.player_season_combo)
        self.layout.insertWidget(max(name_index, 0), self.player_name_row)
        self._season_change_callback = None
        self.player_season_combo.currentIndexChanged.connect(self._handle_player_season_change)

        self.platoon_box = QGroupBox("Platoon Splits")
        platoon_layout = QVBoxLayout(self.platoon_box)
        self.platoon_table = QTableWidget(2, 6)
        self.platoon_table.setHorizontalHeaderLabels(["상대", "AVG", "OBP", "SLG", "OPS", "wRC+"])
        self.platoon_table.verticalHeader().setVisible(False)
        self.platoon_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.platoon_table.setAlternatingRowColors(True)
        self.platoon_table.setMaximumHeight(145)
        platoon_layout.addWidget(self.platoon_table)
        self.platoon_note = QLabel("")
        self.platoon_note.setObjectName("subtitle")
        self.platoon_note.setWordWrap(True)
        platoon_layout.addWidget(self.platoon_note)

        anchor = getattr(self, "running_box", self.defense_box)
        anchor_index = self.layout.indexOf(anchor)
        self.layout.insertWidget(anchor_index + 1, self.platoon_box)
        self.platoon_box.hide()

    def show_batter_with_platoon(self: PlayerView, bundle: Any) -> None:
        original_show_batter(self, bundle)
        self.platoon_box.show()
        self._fill_platoon_table(bundle, False)

    def show_pitcher_with_platoon(
        self: PlayerView, bundle: Any, period_payload: dict[str, Any] | None = None
    ) -> None:
        original_show_pitcher(self, bundle, period_payload)
        self.platoon_box.show()
        self._fill_platoon_table(bundle, True)

    def controller_init_with_season(self: AppController, window: Any, db: Any) -> None:
        original_controller_init(self, window, db)
        self.selected_player_season: int | None = None
        self._player_seasons: dict[int, list[int]] = {}
        self.window.player_view._season_change_callback = self._select_player_season

    def select_player_season(self: AppController, season: int) -> None:
        if self.selected_player_id is None:
            return
        try:
            year = int(season)
        except (TypeError, ValueError):
            return
        if self.selected_player_season == year or self._player_busy:
            return
        self.load_player(self.selected_player_id, year)

    def load_player_with_season(
        self: AppController, player_id: int, season: int | None = None
    ) -> None:
        same_player = self.selected_player_id == player_id
        if self._player_busy and same_player:
            return
        if not same_player:
            self.selected_player_season = None
        self.selected_player_id = player_id
        self._player_busy = True
        self.window.show_player_loading(player_id)
        requested_season = int(season) if season is not None else self.selected_player_season

        async def task() -> tuple[Any, list[int], int]:
            seasons = self._player_seasons.get(player_id)
            if not seasons:
                seasons = await _available_player_seasons(player_id)
            if requested_season is not None and requested_season in seasons:
                target = requested_season
            else:
                target = _choose_default_season(seasons)
            bundle = await self.players.get_bundle(player_id, target)
            return bundle, seasons, target

        def success(payload: tuple[Any, list[int], int]) -> None:
            self._player_busy = False
            bundle, seasons, target = payload
            if self.selected_player_id != player_id:
                return
            self._player_seasons[player_id] = seasons
            self.selected_player_season = target
            self.window.player_view.set_available_seasons(seasons, target)
            self.window.show_player(bundle)
            self.window.set_busy(f"Player data loaded: {bundle.profile.full_name} · {target}")
            if bundle.profile.is_pitcher:
                period = self.window.player_view.current_pitcher_statcast_period
                if period != "yearly":
                    self.load_pitcher_statcast_period(period)
            else:
                period = self.window.player_view.current_trend_period
                if period != "yearly":
                    self.load_player_trend(period)

        def failure(message: str) -> None:
            self._player_busy = False
            self._default_error(message)

        self._run(task, success, on_error=failure)

    def load_trend_for_selected_season(self: AppController, period: str) -> None:
        original = self.season
        if self.selected_player_season is not None:
            self.season = self.selected_player_season
        try:
            original_load_trend(self, period)
        finally:
            self.season = original

    def load_pitcher_period_for_selected_season(self: AppController, period: str) -> None:
        original = self.season
        if self.selected_player_season is not None:
            self.season = self.selected_player_season
        try:
            original_load_pitcher_period(self, period)
        finally:
            self.season = original

    PlayerService.search = search_with_contains_fallback  # type: ignore[method-assign]
    PlayerService.get_bundle = get_bundle_with_platoon  # type: ignore[method-assign]

    MainWindow.__init__ = init_main_with_contains  # type: ignore[method-assign]
    MainWindow._on_search_enter = main_search_enter_contains  # type: ignore[method-assign]
    CompareView.__init__ = init_compare_with_contains  # type: ignore[method-assign]
    CompareView._on_search_enter = compare_search_enter_contains  # type: ignore[method-assign]

    PlayerView.__init__ = init_player_with_season_and_platoon  # type: ignore[method-assign]
    PlayerView._handle_player_season_change = handle_player_season_change  # type: ignore[attr-defined]
    PlayerView.set_available_seasons = set_available_seasons  # type: ignore[attr-defined]
    PlayerView._fill_platoon_table = fill_platoon_table  # type: ignore[attr-defined]
    PlayerView._show_batter = show_batter_with_platoon  # type: ignore[method-assign]
    PlayerView._show_pitcher = show_pitcher_with_platoon  # type: ignore[method-assign]

    AppController.__init__ = controller_init_with_season  # type: ignore[method-assign]
    AppController._select_player_season = select_player_season  # type: ignore[attr-defined]
    AppController.load_player = load_player_with_season  # type: ignore[method-assign]
    AppController.load_player_trend = load_trend_for_selected_season  # type: ignore[method-assign]
    AppController.load_pitcher_statcast_period = load_pitcher_period_for_selected_season  # type: ignore[method-assign]

    PlayerService._player_enhancements_installed = True  # type: ignore[attr-defined]
