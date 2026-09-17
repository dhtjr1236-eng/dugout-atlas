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
        if not value or value in {"—", "-", "--", "---"}:
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
        result[metric] = next(
            (
                parsed
                for name in names
                if (parsed := _safe_float(canonical.get(_canonical_key(name)))) is not None
            ),
            None,
        )
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
    current = int(current_year or date.today().year)
    valid = sorted({int(year) for year in seasons if int(year) > 0}, reverse=True)
    return current if current in valid else valid[0] if valid else current


def _format_rate(value: Any, *, wrc: bool = False) -> str:
    number = _safe_float(value)
    if number is None:
        return "—"
    return f"{number:.0f}" if wrc and abs(number - round(number)) < 0.05 else f"{number:.1f}" if wrc else f"{number:.3f}"


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
    return sorted(unique.values(), key=lambda row: _search_score(str(row.get("name", "")), query))[:limit]


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
        rows = []
        for person in payload.get("people", []) or []:
            try:
                player_id = int(person.get("id", 0) or 0)
            except (TypeError, ValueError):
                continue
            if not player_id:
                continue
            position = person.get("primaryPosition", {}) or {}
            rows.append(
                {
                    "id": player_id,
                    "name": str(person.get("fullName", "")),
                    "first_name": str(person.get("firstName", "")),
                    "last_name": str(person.get("lastName", "")),
                    "position": str(position.get("abbreviation", "")),
                    "team": "",
                }
            )
        _ROSTER_CACHE[season] = rows

    needle = _normalize_search_text(query)
    compact = needle.replace(" ", "")
    return [
        row
        for row in rows
        if any(
            needle and needle in _normalize_search_text(value)
            or compact and compact in _normalize_search_text(value).replace(" ", "")
            for value in (row.get("name", ""), row.get("first_name", ""), row.get("last_name", ""))
        )
    ]


async def _available_player_seasons(player_id: int) -> list[int]:
    from config.settings import SETTINGS
    from services.base_http import async_get_json

    base = SETTINGS.mlb_api_base.rstrip("/")

    async def fetch(group: str) -> dict[str, Any]:
        return await async_get_json(
            f"{base}/v1/people/{int(player_id)}/stats",
            params={"stats": "yearByYear", "group": group, "gameType": "R"},
        )

    payloads = await asyncio.gather(fetch("hitting"), fetch("pitching"), return_exceptions=True)
    years: set[int] = set()
    for payload in payloads:
        if isinstance(payload, Exception):
            LOGGER.info("선수 시즌 목록 조회 일부 실패 player_id=%s: %s", player_id, payload)
            continue
        for bucket in payload.get("stats", []) or []:
            for split in bucket.get("splits", []) or []:
                try:
                    years.add(int(split.get("season")))
                except (TypeError, ValueError):
                    pass
    return sorted(years or {date.today().year}, reverse=True)


def _fetch_fangraphs_split(service: Any, player_id: int, full_name: str, season: int, pitcher: bool, month: str) -> tuple[dict[str, Any], str]:
    import pandas as pd
    from services.dataframe_utils import row_to_dict
    from services.fangraphs_service import FG_LEADERS_URL

    params = service._api_params(int(season), int(season), bool(pitcher))
    params["month"] = month
    payload = service._request_json(FG_LEADERS_URL, params)
    frame = pd.DataFrame(payload.get("data", []) if isinstance(payload.get("data", []), list) else [])
    row = service._find_player_row(frame, int(player_id), full_name)
    return (_extract_metrics(row_to_dict(row)) if row is not None else {}), f"{FG_LEADERS_URL}?{urlencode(params)}"


def _fetch_mlb_split(player_id: int, season: int, pitcher: bool, sit_code: str) -> tuple[dict[str, Any], str]:
    import requests
    from config.settings import SETTINGS

    url = f"{SETTINGS.mlb_api_base.rstrip('/')}/v1/people/{int(player_id)}/stats"
    params = {
        "stats": "statSplits",
        "group": "pitching" if pitcher else "hitting",
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
                if splits:
                    return _extract_metrics(splits[0].get("stat", {}) or {}), str(response.url)
            return {}, str(response.url)
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < SETTINGS.request_retries:
                time.sleep(min(1.5 * attempt, 4.5))
    raise RuntimeError(f"MLB platoon split request failed: {last_error}")


def get_platoon_splits(service: Any, player_id: int, full_name: str, season: int, pitcher: bool) -> dict[str, Any]:
    role = "pitcher" if pitcher else "batter"
    cached = service.db.get_player_stats(player_id, PLATOON_CACHE_SOURCE, season, role, service._cache_ttl_days(season))
    if cached:
        return cached

    labels = {"left": "vs LHB", "right": "vs RHB"} if pitcher else {"left": "vs LHP", "right": "vs RHP"}
    result: dict[str, Any] = {}
    sources: list[dict[str, str]] = []
    errors: list[str] = []
    for side in ("left", "right"):
        fg: dict[str, Any] = {}
        fg_url = ""
        try:
            fg, fg_url = _fetch_fangraphs_split(service, player_id, full_name, season, pitcher, FANGRAPHS_SPLIT_MONTHS[side])
        except Exception as exc:
            errors.append(f"FanGraphs {labels[side]}: {exc}")
        mlb: dict[str, Any] = {}
        mlb_url = ""
        if not all(fg.get(key) is not None for key in ("AVG", "OBP", "SLG", "OPS")):
            try:
                mlb, mlb_url = _fetch_mlb_split(player_id, season, pitcher, MLB_SPLIT_CODES[side])
            except Exception as exc:
                errors.append(f"MLB {labels[side]}: {exc}")
        merged = _merge_missing(fg, mlb)
        merged["label"] = labels[side]
        result[side] = merged
        now = datetime.now(UTC).isoformat(timespec="seconds")
        if fg_url:
            sources.append({"name": f"FanGraphs Platoon Split — {labels[side]}", "url": fg_url, "as_of": now})
        if mlb_url:
            sources.append({"name": f"MLB Stats API Platoon Split — {labels[side]}", "url": mlb_url, "as_of": now})

    available = [any(result[side].get(key) is not None for key in ("AVG", "OBP", "SLG", "OPS", "wRC+")) for side in ("left", "right")]
    result["_status"] = "ok" if all(available) else "partial" if any(available) else "unavailable"
    result["_sources"] = sources
    if errors:
        result["_errors"] = errors
    if any(available):
        service.db.set_player_stats(player_id, PLATOON_CACHE_SOURCE, season, role, result)
    return result


def install_player_enhancements() -> None:
    """검색 보강, 선수 시즌 선택, 좌우 플래툰 스플릿을 기존 화면에 추가한다."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QComboBox, QGroupBox, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
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

    async def search_contains(self: PlayerService, query: str) -> list[dict[str, Any]]:
        rows = list(await original_search(self, query))
        needle = _normalize_search_text(query)
        if not any(needle and needle in _normalize_search_text(row.get("name", "")) for row in rows):
            try:
                rows.extend(await _current_roster_search(query))
            except Exception as exc:
                LOGGER.info("MLB 전체 선수 검색 폴백 실패 query=%r: %s", query, exc)
        return _dedupe_and_rank(rows, query)

    async def bundle_with_platoon(self: PlayerService, player_id: int, season: int):
        bundle = await original_get_bundle(self, player_id, season)
        try:
            platoon = await asyncio.to_thread(get_platoon_splits, self.fangraphs, player_id, bundle.profile.full_name, season, bundle.profile.is_pitcher)
            bundle.fangraphs["_platoon"] = platoon
            bundle.fangraphs.setdefault("_sources", []).extend(platoon.get("_sources", []))
            bundle.errors.extend(f"Platoon: {message}" for message in platoon.get("_errors", []) if message)
        except Exception as exc:
            LOGGER.exception("Platoon split failed player=%s season=%s", player_id, season)
            bundle.errors.append(f"Platoon: {exc}")
        return bundle

    def init_main(self: MainWindow) -> None:
        original_main_init(self)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)

    def main_enter(self: MainWindow) -> None:
        text = _normalize_search_text(self.search.text())
        matches = [(_search_score(label.split(" — ", 1)[0], text), pid) for label, pid in self._search_map.items() if text in _normalize_search_text(label.split(" — ", 1)[0])]
        if matches:
            self.search_player_selected.emit(sorted(matches)[0][1])

    def init_compare(self: CompareView) -> None:
        original_compare_init(self)
        for completer in self._completers.values():
            completer.setFilterMode(Qt.MatchFlag.MatchContains)

    def compare_enter(self: CompareView, slot: int) -> None:
        text = _normalize_search_text(self.current_query(slot))
        matches = [(_search_score(label.split(" — ", 1)[0], text), pid) for label, pid in self._search_maps.get(slot, {}).items() if text in _normalize_search_text(label.split(" — ", 1)[0])]
        if matches:
            self.player_selected.emit(slot, sorted(matches)[0][1])

    def season_changed(self: PlayerView) -> None:
        if self.player_season_combo.signalsBlocked():
            return
        try:
            season = int(self.player_season_combo.currentData())
        except (TypeError, ValueError):
            return
        callback = getattr(self, "_season_change_callback", None)
        if callable(callback):
            callback(season)

    def set_seasons(self: PlayerView, seasons: list[int], selected: int) -> None:
        values = sorted({int(year) for year in seasons if int(year) > 0}, reverse=True)
        if selected not in values:
            values.insert(0, selected)
        self.player_season_combo.blockSignals(True)
        self.player_season_combo.clear()
        for year in values:
            self.player_season_combo.addItem(str(year), year)
        self.player_season_combo.setCurrentIndex(max(self.player_season_combo.findData(selected), 0))
        self.player_season_combo.setEnabled(bool(values))
        self.player_season_combo.blockSignals(False)

    def fill_platoon(self: PlayerView, bundle: Any, pitcher: bool) -> None:
        platoon = bundle.fangraphs.get("_platoon", {}) if isinstance(bundle.fangraphs, dict) else {}
        defaults = ("vs LHB", "vs RHB") if pitcher else ("vs LHP", "vs RHP")
        for row_index, side in enumerate(("left", "right")):
            split = platoon.get(side, {}) if isinstance(platoon, dict) else {}
            values = [str(split.get("label") or defaults[row_index]), _format_rate(split.get("AVG")), _format_rate(split.get("OBP")), _format_rate(split.get("SLG")), _format_rate(split.get("OPS")), _format_rate(split.get("wRC+"), wrc=True)]
            for col, value in enumerate(values):
                self.platoon_table.setItem(row_index, col, QTableWidgetItem(value))
        self.platoon_note.setText("좌/우 상대 성적은 FanGraphs split을 우선 사용하고, 누락된 slash line은 MLB Stats API로 보완합니다.")

    def init_player(self: PlayerView) -> None:
        original_player_init(self)
        name_index = self.layout.indexOf(self.name_label)
        self.layout.removeWidget(self.name_label)
        row = QWidget(self.content)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self.name_label)
        row_layout.addStretch()
        row_layout.addWidget(QLabel("시즌"))
        self.player_season_combo = QComboBox()
        self.player_season_combo.setMinimumWidth(92)
        self.player_season_combo.setEnabled(False)
        row_layout.addWidget(self.player_season_combo)
        self.layout.insertWidget(max(name_index, 0), row)
        self._season_change_callback = None
        self.player_season_combo.currentIndexChanged.connect(self._handle_player_season_change)

        self.platoon_box = QGroupBox("Platoon Splits")
        platoon_layout = QVBoxLayout(self.platoon_box)
        self.platoon_table = QTableWidget(2, 6)
        self.platoon_table.setHorizontalHeaderLabels(["상대", "AVG", "OBP", "SLG", "OPS", "wRC+"])
        self.platoon_table.verticalHeader().setVisible(False)
        self.platoon_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.platoon_table.setMaximumHeight(145)
        platoon_layout.addWidget(self.platoon_table)
        self.platoon_note = QLabel("")
        self.platoon_note.setWordWrap(True)
        self.platoon_note.setObjectName("subtitle")
        platoon_layout.addWidget(self.platoon_note)
        anchor = getattr(self, "running_box", self.defense_box)
        self.layout.insertWidget(self.layout.indexOf(anchor) + 1, self.platoon_box)
        self.platoon_box.hide()

    def show_batter(self: PlayerView, bundle: Any) -> None:
        original_show_batter(self, bundle)
        self.platoon_box.show()
        self._fill_platoon_table(bundle, False)

    def show_pitcher(self: PlayerView, bundle: Any, period_payload: dict[str, Any] | None = None) -> None:
        original_show_pitcher(self, bundle, period_payload)
        self.platoon_box.show()
        self._fill_platoon_table(bundle, True)

    def controller_init(self: AppController, window: Any, db: Any) -> None:
        original_controller_init(self, window, db)
        self.selected_player_season: int | None = None
        self._player_seasons: dict[int, list[int]] = {}
        self.window.player_view._season_change_callback = self._select_player_season

    def select_season(self: AppController, season: int) -> None:
        if self.selected_player_id is not None and not self._player_busy and self.selected_player_season != season:
            self.load_player(self.selected_player_id, season)

    def load_player(self: AppController, player_id: int, season: int | None = None) -> None:
        same_player = self.selected_player_id == player_id
        if self._player_busy and same_player:
            return
        if not same_player:
            self.selected_player_season = None
        self.selected_player_id = player_id
        self._player_busy = True
        self.window.show_player_loading(player_id)
        requested = int(season) if season is not None else self.selected_player_season

        async def task() -> tuple[Any, list[int], int]:
            seasons = self._player_seasons.get(player_id) or await _available_player_seasons(player_id)
            target = requested if requested in seasons else _choose_default_season(seasons)
            return await self.players.get_bundle(player_id, target), seasons, target

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

        def failure(message: str) -> None:
            self._player_busy = False
            self._default_error(message)

        self._run(task, success, on_error=failure)

    def trend_selected_season(self: AppController, period: str) -> None:
        original = self.season
        self.season = self.selected_player_season or self.season
        try:
            original_load_trend(self, period)
        finally:
            self.season = original

    def pitcher_selected_season(self: AppController, period: str) -> None:
        original = self.season
        self.season = self.selected_player_season or self.season
        try:
            original_load_pitcher_period(self, period)
        finally:
            self.season = original

    PlayerService.search = search_contains  # type: ignore[method-assign]
    PlayerService.get_bundle = bundle_with_platoon  # type: ignore[method-assign]
    MainWindow.__init__ = init_main  # type: ignore[method-assign]
    MainWindow._on_search_enter = main_enter  # type: ignore[method-assign]
    CompareView.__init__ = init_compare  # type: ignore[method-assign]
    CompareView._on_search_enter = compare_enter  # type: ignore[method-assign]
    PlayerView.__init__ = init_player  # type: ignore[method-assign]
    PlayerView._handle_player_season_change = season_changed  # type: ignore[attr-defined]
    PlayerView.set_available_seasons = set_seasons  # type: ignore[attr-defined]
    PlayerView._fill_platoon_table = fill_platoon  # type: ignore[attr-defined]
    PlayerView._show_batter = show_batter  # type: ignore[method-assign]
    PlayerView._show_pitcher = show_pitcher  # type: ignore[method-assign]
    AppController.__init__ = controller_init  # type: ignore[method-assign]
    AppController._select_player_season = select_season  # type: ignore[attr-defined]
    AppController.load_player = load_player  # type: ignore[method-assign]
    AppController.load_player_trend = trend_selected_season  # type: ignore[method-assign]
    AppController.load_pitcher_statcast_period = pitcher_selected_season  # type: ignore[method-assign]
    PlayerService._player_enhancements_installed = True  # type: ignore[attr-defined]
