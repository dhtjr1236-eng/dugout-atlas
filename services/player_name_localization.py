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
from services.team_localization import apply_team_ref, localized_team_name

LOGGER = logging.getLogger(__name__)
from config.paths import resource_path, data_path
SEED_PATH = resource_path("config", "player_names_seed.json")
CACHE_PATH = DATA_DIR / "player_name_locales.json"
MLB_PLAYER_PAGE = "https://www.mlb.com/{locale}/player/{slug}-{player_id}"


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return "".join(ch for ch in value if ch.isalnum())


def _slug(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower() or "player"


def extract_mlb_locale_player_name(page_html: str, language: str) -> str | None:
    """Return only the localized player name from MLB locale page metadata."""
    patterns = (
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
        r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']',
        r"<title[^>]*>(.*?)</title>",
    )
    suffixes = (
        " Stats,", " Stats |", " Statistics,", " Player Profile", " Fantasy News",
        " 통계", " 기록", " 統計", " 成績", " | MLB", " - MLB",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, page_html, re.I | re.S):
            text = html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()
            for marker in suffixes:
                pos = text.find(marker)
                if pos > 0:
                    text = text[:pos].strip()
            text = re.sub(r"\s+#\d+\s*$", "", text).strip()
            if text and len(text) <= 80 and "MLB.com" not in text:
                return text
    return None


_KANA = {
    "ア":"아","イ":"이","ウ":"우","エ":"에","オ":"오","カ":"카","キ":"키","ク":"쿠","ケ":"케","コ":"코",
    "ガ":"가","ギ":"기","グ":"구","ゲ":"게","ゴ":"고","サ":"사","シ":"시","ス":"스","セ":"세","ソ":"소",
    "ザ":"자","ジ":"지","ズ":"즈","ゼ":"제","ゾ":"조","タ":"타","チ":"치","ツ":"츠","テ":"테","ト":"토",
    "ダ":"다","デ":"데","ド":"도","ナ":"나","ニ":"니","ヌ":"누","ネ":"네","ノ":"노","ハ":"하","ヒ":"히",
    "フ":"프","ヘ":"헤","ホ":"호","バ":"바","ビ":"비","ブ":"부","ベ":"베","ボ":"보","パ":"파","ピ":"피",
    "プ":"푸","ペ":"페","ポ":"포","マ":"마","ミ":"미","ム":"무","メ":"메","モ":"모","ヤ":"야","ユ":"유",
    "ヨ":"요","ラ":"라","リ":"리","ル":"루","レ":"레","ロ":"로","ワ":"와","ン":"ㄴ",
}
_DIGRAPHS = {
    "キャ":"캬","キュ":"큐","キョ":"쿄","シャ":"샤","シュ":"슈","ショ":"쇼","ジャ":"자","ジュ":"주","ジョ":"조",
    "チャ":"차","チュ":"추","チョ":"초","ニャ":"냐","ニュ":"뉴","ニョ":"뇨","リャ":"랴","リュ":"류","リョ":"료",
    "ファ":"파","フィ":"피","フェ":"페","フォ":"포","ティ":"티","ディ":"디","ウィ":"위","ウェ":"웨","ウォ":"워",
}

def katakana_to_hangul(value: str) -> str:
    text=str(value or "").strip()
    out=""; i=0
    while i < len(text):
        two=text[i:i+2]
        if two in _DIGRAPHS:
            out += _DIGRAPHS[two]; i += 2; continue
        ch=text[i]
        if ch in {"・","･"}:
            out += " "
        elif ch.isspace():
            if out and not out.endswith(" "): out += " "
        elif ch in {"ッ","ー"}:
            pass
        else:
            out += _KANA.get(ch,ch)
        i += 1
    return re.sub(r"\s+"," ",out).strip()


class PlayerNameLocalizer:
    def __init__(self, seed_path: Path = SEED_PATH, cache_path: Path = CACHE_PATH, override_path: Path | None = None) -> None:
        self.seed_path = Path(seed_path)
        self.cache_path = Path(cache_path)
        self.seed = self._read(self.seed_path)
        self.cache = self._read(self.cache_path)
        self.players = [row for row in self.seed.get("players", []) if isinstance(row, dict)]
        self._load_override(override_path if override_path is not None else data_path("config", "player_names_override.json", create_parent=False))
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": SETTINGS.user_agent})

    def _load_override(self, path: Path) -> None:
        """Merge validated display names; never change provider ID matching."""
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            rows = payload.get("players") if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                raise ValueError("Expected players list")
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("en"), str) or not row["en"].strip():
                    raise ValueError("Expected English name")
                if any(k in row and (not isinstance(row[k], str) or not row[k].strip()) for k in ("ko", "ja")):
                    raise ValueError("Expected display name string")
                if any(k not in {"en", "ko", "ja"} for k in row):
                    raise ValueError("Unsupported override field")
            merged = {_norm(row.get("en", "")): dict(row) for row in self.players}
            for row in rows:
                key = _norm(row["en"])
                entry = merged.setdefault(key, {})
                entry.update(row)
                entry["locked_locales"] = sorted(set(entry.get("locked_locales", [])) | set(row))
            self.players = list(merged.values())
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError):
            LOGGER.warning("Invalid or unreadable player name override; using seed names")

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def language() -> str:
        language = str(read_preferences().get("language", "en"))
        return language if language in {"en", "ko", "ja"} else "en"

    def seed_entry(self, english_name: str) -> dict[str, Any]:
        needle = _norm(english_name)
        for row in self.players:
            names = [row.get("en", ""), row.get("ko", ""), row.get("ja", ""), *(row.get("aliases", []) or [])]
            if any(_norm(str(name)) == needle for name in names if name):
                return row
        return {}

    @staticmethod
    def _sanitize_cached_display_name(value: Any) -> str:
        text=str(value or "").strip()
        for marker in (" Stats,"," Stats |"," Statistics,"," Player Profile"," Fantasy News"," | MLB"," - MLB"):
            pos=text.find(marker)
            if pos > 0: text=text[:pos].strip()
        return text

    def display_name(self, player_id: int, english_name: str, language: str | None = None) -> str:
        language = language or str(read_preferences().get("language", "en"))
        seed = self.seed_entry(english_name)
        if language == "en":
            return str(seed.get("en") or english_name) if "en" in (seed.get("locked_locales") or []) else english_name
        if language in (seed.get("locked_locales") or []):
            return str(seed.get(language) or english_name)
        cached = self.cache.get(str(int(player_id)), {})
        cached_name = self._sanitize_cached_display_name(cached.get(language))
        if cached_name:
            return cached_name
        seeded = str(seed.get(language) or "").strip()
        if seeded:
            return seeded
        if language == "ko":
            japanese = self._sanitize_cached_display_name(cached.get("ja"))
            derived = katakana_to_hangul(japanese)
            if derived and derived != japanese:
                return derived
        return english_name

    def display_team(self, english_name: str, team: str, season: int = 2026) -> str:
        explicit = str(self.seed_entry(english_name).get(f"team_{season}") or team or "")
        return localized_team_name(None, explicit, self.language(), short=False)

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
            values = [row.get("en", ""), row.get("ko",""), row.get("ja",""), *(row.get("aliases", []) or [])]
            for value in values:
                source = str(value or "").strip()
                if source and source != target and source not in target:
                    pairs.append((source, target))
        for cached in self.cache.values():
            if not isinstance(cached, dict):
                continue
            seed = self.seed_entry(str(cached.get("en") or ""))
            target = str(seed.get(language) or "") if language in (seed.get("locked_locales") or []) else self._sanitize_cached_display_name(cached.get(language))
            if not target and language == "ko":
                target = katakana_to_hangul(self._sanitize_cached_display_name(cached.get("ja")))
            if not target:
                continue
            for value in (cached.get("en"), cached.get("ko"), cached.get("ja")):
                source=self._sanitize_cached_display_name(value)
                if source and source != target and source not in target:
                    pairs.append((source,target))
        pairs.sort(key=lambda item: len(item[0]), reverse=True)
        return list(dict.fromkeys(pairs))

    def _fetch_locale_name(self, player_id: int, english_name: str, language: str) -> tuple[str | None, str]:
        url = MLB_PLAYER_PAGE.format(locale=language, slug=quote(_slug(english_name)), player_id=player_id)
        try:
            response=self.session.get(url,timeout=min(15,SETTINGS.request_timeout_seconds),allow_redirects=True)
            response.raise_for_status()
            name=extract_mlb_locale_player_name(response.text,language)
        except requests.RequestException:
            return None,url
        name=self._sanitize_cached_display_name(name)
        if not name or _norm(name)==_norm(english_name):
            return None,url
        return name,url

    def ensure_official_names(self, player_id: int, english_name: str, *, languages: tuple[str,...] | None = None) -> None:
        seed=self.seed_entry(english_name)
        current=dict(self.cache.get(str(player_id),{}))
        wanted=languages or ("ko","ja")
        changed=False
        for language in wanted:
            if language not in {"ko","ja"} or language in (seed.get("locked_locales") or []):
                continue
            if seed.get(language) or current.get(language):
                continue
            name,url=self._fetch_locale_name(player_id,english_name,language)
            if name:
                current[language]=name; current[f"{language}_source"]=url; changed=True
        if "ko" in wanted and not seed.get("ko") and not current.get("ko"):
            japanese=self._sanitize_cached_display_name(current.get("ja"))
            ja_url=""
            if not japanese:
                japanese,ja_url=self._fetch_locale_name(player_id,english_name,"ja")
                if japanese:
                    current["ja"]=japanese; current["ja_source"]=ja_url; changed=True
            korean=katakana_to_hangul(japanese)
            if korean and korean != japanese:
                current["ko"]=korean
                current["ko_source"]="derived-from-mlb-japan-katakana"
                changed=True
        if changed:
            current["en"]=english_name
            self.cache[str(player_id)]=current
            self.cache_path.parent.mkdir(parents=True,exist_ok=True)
            temp=self.cache_path.with_suffix(".tmp")
            temp.write_text(json.dumps(self.cache,ensure_ascii=False,indent=2),encoding="utf-8")
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


def _apply_localized_game_detail(detail: Any, language: str) -> None:
    people=(
        getattr(detail,"batter",None), getattr(detail,"pitcher",None),
        *getattr(detail,"away_lineup",[]), *getattr(detail,"home_lineup",[]),
        *getattr(detail,"away_pitchers",[]), *getattr(detail,"home_pitchers",[]),
    )
    for person in people:
        if person is None: continue
        try: pid=int(person.id)
        except (AttributeError,TypeError,ValueError): continue
        person.name=localized_player_name(pid,str(person.name),language)
    apply_team_ref(detail.away,language); apply_team_ref(detail.home,language)


def install_player_name_localization() -> None:
    from PyQt6.QtCore import QTimer
    from services.player_service import PlayerService
    from services.mlb_api import MLBApiService
    from ui.compare_view import CompareView
    from ui.game_view import GameView
    from ui.lineup_view import LineupView
    from ui.main_window import MainWindow
    from ui.player_view import PlayerView

    if getattr(PlayerService, "_player_name_localization_installed", False):
        return

    original_search = PlayerService.search
    original_live_game = MLBApiService.get_live_game
    original_schedule = MLBApiService.get_schedule
    original_standings = MLBApiService.get_standings
    original_league_team_stats = MLBApiService.get_league_team_stats
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
        language=LOCALIZER.language()
        wanted=("ko","ja") if language=="ko" else (("ja",) if language=="ja" else ("ko","ja"))
        await asyncio.to_thread(LOCALIZER.ensure_official_names,bundle.profile.id,bundle.profile.full_name,languages=wanted)
        return bundle

    async def localized_live_game(self: MLBApiService, game_pk: int) -> Any:
        detail=await original_live_game(self,game_pk)
        language=LOCALIZER.language()
        if language in {"ko","ja"}:
            people={}
            for person in (detail.batter,detail.pitcher,*detail.away_lineup,*detail.home_lineup,*detail.away_pitchers,*detail.home_pitchers):
                if person is not None and getattr(person,"id",0) and getattr(person,"name",""):
                    people[int(person.id)]=str(person.name)
            wanted=("ko","ja") if language=="ko" else ("ja",)
            await asyncio.gather(*(asyncio.to_thread(LOCALIZER.ensure_official_names,pid,name,languages=wanted) for pid,name in people.items()),return_exceptions=True)
            _apply_localized_game_detail(detail,language)
        return detail

    async def localized_schedule(self: MLBApiService, game_date: Any) -> list[Any]:
        games=await original_schedule(self,game_date)
        language=LOCALIZER.language()
        if language in {"ko","ja"}:
            for game in games:
                apply_team_ref(game.away,language); apply_team_ref(game.home,language)
        return games

    async def localized_standings(self: MLBApiService, season: int, standings_type: str="regularSeason") -> list[dict[str,Any]]:
        rows=await original_standings(self,season,standings_type)
        language=LOCALIZER.language()
        if language in {"ko","ja"}:
            for row in rows:
                row["team"]=localized_team_name(int(row.get("team_id",0) or 0),str(row.get("team","")),language)
        return rows

    async def localized_league_stats(self: MLBApiService, season: int) -> list[dict[str,Any]]:
        rows=await original_league_team_stats(self,season)
        language=LOCALIZER.language()
        if language in {"ko","ja"}:
            for row in rows:
                row["team"]=localized_team_name(int(row.get("team_id",0) or 0),str(row.get("team","")),language)
        return rows

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

    MLBApiService.get_live_game = localized_live_game  # type: ignore[method-assign]
    MLBApiService.get_schedule = localized_schedule  # type: ignore[method-assign]
    MLBApiService.get_standings = localized_standings  # type: ignore[method-assign]
    MLBApiService.get_league_team_stats = localized_league_stats  # type: ignore[method-assign]
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
