from __future__ import annotations

import asyncio
import html
import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from config.preferences import read_preferences
from config.settings import DATA_DIR, SETTINGS

LOGGER = logging.getLogger(__name__)
SEED_PATH = Path(__file__).resolve().parent.parent / "config" / "player_names_seed.json"
CACHE_PATH = DATA_DIR / "player_name_locales.json"
MLB_PLAYER_PAGE = "https://www.mlb.com/{locale}/player/{slug}-{player_id}"


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return "".join(ch for ch in value if ch.isalnum())


def _slug(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower() or "player"


def extract_mlb_locale_player_name(page_html: str, language: str) -> str | None:
    patterns = (
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
        r"<title[^>]*>(.*?)</title>",
    )
    markers = {
        "ko": (" 통계", " 기록", " | MLB", " - MLB"),
        "ja": (" 統計", " 成績", " | MLB", " - MLB"),
    }.get(language, (" | MLB", " - MLB"))
    for pattern in patterns:
        match = re.search(pattern, page_html, re.I | re.S)
        if not match:
            continue
        text = html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()
        for marker in markers:
            if marker in text:
                text = text.split(marker, 1)[0].strip()
        if text and len(text) <= 80 and "MLB.com" not in text:
            return text
    return None


class PlayerNameLocalizer:
    def __init__(self, seed_path: Path = SEED_PATH, cache_path: Path = CACHE_PATH) -> None:
        self.seed_path = Path(seed_path)
        self.cache_path = Path(cache_path)
        self.seed = self._read(self.seed_path)
        self.cache = self._read(self.cache_path)
        self.players = [row for row in self.seed.get("players", []) if isinstance(row, dict)]
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": SETTINGS.user_agent})

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def seed_entry(self, english_name: str) -> dict[str, Any]:
        needle = _norm(english_name)
        for row in self.players:
            names = [row.get("en", ""), *(row.get("aliases", []) or [])]
            if any(_norm(str(name)) == needle for name in names if name):
                return row
        return {}

    def display_name(self, player_id: int, english_name: str, language: str | None = None) -> str:
        language = language or str(read_preferences().get("language", "en"))
        if language == "en":
            return english_name
        seed = self.seed_entry(english_name)
        if language in (seed.get("locked_locales") or []):
            return str(seed.get(language) or english_name)
        cached = self.cache.get(str(int(player_id)), {})
        return str(cached.get(language) or seed.get(language) or english_name)

    def display_team(self, english_name: str, team: str, season: int = 2026) -> str:
        return str(self.seed_entry(english_name).get(f"team_{season}") or team or "")

    def alias_english_names(self, query: str) -> list[str]:
        needle = _norm(query)
        if len(needle) < 2:
            return []
        found: list[str] = []
        for row in self.players:
            values = [row.get("en", ""), row.get("ko", ""), row.get("ja", ""), *(row.get("aliases", []) or [])]
            if any(needle in _norm(str(value)) for value in values if value):
                name = str(row.get("en") or "")
                if name and name not in found:
                    found.append(name)
        return found

    def replacement_pairs(self) -> list[tuple[str, str]]:
        language = str(read_preferences().get("language", "en"))
        pairs: list[tuple[str, str]] = []
        for row in self.players:
            target = str(row.get(language) or row.get("en") or "")
            if not target:
                continue
            values = [row.get("en", ""), *(row.get("aliases", []) or [])]
            for value in values:
                source = str(value or "").strip()
                # Critical v1.41 invariant: never replace a substring already contained
                # in the localized target (e.g. ジョンフ inside イ・ジョンフ).
                if source and source != target and source not in target:
                    pairs.append((source, target))
        pairs.sort(key=lambda item: len(item[0]), reverse=True)
        return pairs

    def ensure_official_names(self, player_id: int, english_name: str) -> None:
        seed = self.seed_entry(english_name)
        current = dict(self.cache.get(str(player_id), {}))
        changed = False
        for language in ("ko", "ja"):
            if language in (seed.get("locked_locales") or []) or current.get(language) or seed.get(language):
                continue
            url = MLB_PLAYER_PAGE.format(locale=language, slug=quote(_slug(english_name)), player_id=player_id)
            try:
                response = self.session.get(url, timeout=min(15, SETTINGS.request_timeout_seconds))
                response.raise_for_status()
                name = extract_mlb_locale_player_name(response.text, language)
            except requests.RequestException:
                continue
            if name and _norm(name) != _norm(english_name):
                current[language] = name
                current[f"{language}_source"] = url
                changed = True
        if changed:
            current["en"] = english_name
            self.cache[str(player_id)] = current
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.cache_path.with_suffix(".tmp")
            temp.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(self.cache_path)


LOCALIZER = PlayerNameLocalizer()


def localized_player_name(player_id: int, english_name: str, language: str | None = None) -> str:
    return LOCALIZER.display_name(player_id, english_name, language)


def _replace_names(text: str) -> str:
    result = str(text or "")
    for source, target in LOCALIZER.replacement_pairs():
        result = result.replace(source, target)
    return result


def _replace_widget_tree(root: Any) -> None:
    from PyQt6.QtWidgets import QAbstractButton, QGroupBox, QLabel, QListWidget, QTableWidget, QWidget
    widgets = [root, *root.findChildren(QWidget)]
    for widget in widgets:
        if isinstance(widget, QLabel):
            widget.setText(_replace_names(widget.text()))
        elif isinstance(widget, QAbstractButton):
            widget.setText(_replace_names(widget.text()))
        elif isinstance(widget, QGroupBox):
            widget.setTitle(_replace_names(widget.title()))
        elif isinstance(widget, QListWidget):
            for index in range(widget.count()):
                widget.item(index).setText(_replace_names(widget.item(index).text()))
        elif isinstance(widget, QTableWidget):
            for row in range(widget.rowCount()):
                for col in range(widget.columnCount()):
                    item = widget.item(row, col)
                    if item is not None:
                        item.setText(_replace_names(item.text()))


def install_player_name_localization() -> None:
    from PyQt6.QtCore import QTimer
    from services.player_service import PlayerService
    from ui.compare_view import CompareView
    from ui.game_view import GameView
    from ui.lineup_view import LineupView
    from ui.main_window import MainWindow
    from ui.player_view import PlayerView

    if getattr(PlayerService, "_player_name_localization_installed", False):
        return

    original_search = PlayerService.search
    original_bundle = PlayerService.get_bundle
    original_main_results = MainWindow.update_search_results
    original_player_bundle = PlayerView.set_bundle
    original_compare_results = CompareView.update_search_results
    original_compare_set = CompareView.set_player
    original_compare_render = CompareView._render
    original_lineup = LineupView.set_game
    original_game = GameView.set_game

    async def search(self: PlayerService, query: str) -> list[dict[str, Any]]:
        rows = await original_search(self, query)
        by_id = {int(row.get("id", 0)): dict(row) for row in rows if int(row.get("id", 0))}
        for english_name in LOCALIZER.alias_english_names(query):
            try:
                extra = await original_search(self, english_name)
            except Exception:
                continue
            for row in extra:
                player_id = int(row.get("id", 0) or 0)
                if player_id:
                    by_id[player_id] = dict(row)
        return list(by_id.values())[:10]

    async def get_bundle(self: PlayerService, player_id: int, season: int) -> Any:
        bundle = await original_bundle(self, player_id, season)
        await asyncio.to_thread(LOCALIZER.ensure_official_names, bundle.profile.id, bundle.profile.full_name)
        return bundle

    def localize_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
        output = []
        for row in rows:
            copy = dict(row)
            pid = int(copy.get("id", 0) or 0)
            english = str(copy.get("name", "") or "")
            copy["name"] = localized_player_name(pid, english)
            copy["team"] = LOCALIZER.display_team(english, str(copy.get("team", "") or ""), 2026)
            output.append(copy)
        return output

    def main_results(self: MainWindow, rows: list[dict[str, object]]) -> None:
        self._localized_search_rows = [dict(row) for row in rows]
        original_main_results(self, localize_rows(rows))

    def player_bundle(self: PlayerView, bundle: Any) -> None:
        original_player_bundle(self, bundle)
        profile = bundle.profile
        self.name_label.setText(localized_player_name(profile.id, profile.full_name))
        team = LOCALIZER.display_team(profile.full_name, profile.team, 2026)
        hand = f"Bats: {profile.bats or '—'}  |  Throws: {profile.throws or '—'}"
        self.profile_label.setText(f"{team or '—'}  |  {profile.position or '—'}  |  Age {profile.age or '—'}  |  {hand}")

    def compare_results(self: CompareView, slot: int, rows: list[dict[str, object]]) -> None:
        store = getattr(self, "_localized_search_rows", {})
        store[slot] = [dict(row) for row in rows]
        self._localized_search_rows = store
        original_compare_results(self, slot, localize_rows(rows))

    def compare_set(self: CompareView, slot: int, bundle: Any) -> None:
        original_compare_set(self, slot, bundle)
        _replace_widget_tree(self)

    def compare_render(self: CompareView) -> None:
        original_compare_render(self)
        _replace_widget_tree(self)

    def lineup(self: LineupView, detail: Any) -> None:
        original_lineup(self, detail)
        _replace_widget_tree(self)

    def game(self: GameView, detail: Any) -> None:
        original_game(self, detail)
        _replace_widget_tree(self)

    PlayerService.search = search  # type: ignore[method-assign]
    PlayerService.get_bundle = get_bundle  # type: ignore[method-assign]
    MainWindow.update_search_results = main_results  # type: ignore[method-assign]
    PlayerView.set_bundle = player_bundle  # type: ignore[method-assign]
    CompareView.update_search_results = compare_results  # type: ignore[method-assign]
    CompareView.set_player = compare_set  # type: ignore[method-assign]
    CompareView._render = compare_render  # type: ignore[method-assign]
    LineupView.set_game = lineup  # type: ignore[method-assign]
    GameView.set_game = game  # type: ignore[method-assign]

    try:
        import ui.settings_dialog as settings_dialog
        original_set_language = settings_dialog.set_language

        def set_language(language: str) -> None:
            original_set_language(language)
            QTimer.singleShot(0, lambda: [_replace_widget_tree(w) for w in __import__("PyQt6.QtWidgets", fromlist=["QApplication"]).QApplication.topLevelWidgets()])

        settings_dialog.set_language = set_language
    except Exception:
        LOGGER.exception("player-name language refresh hook failed")

    PlayerService._player_name_localization_installed = True  # type: ignore[attr-defined]
