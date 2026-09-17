from __future__ import annotations

from typing import Any


EVENT_CODES = {
    "home_run": "HR",
    "single": "1B",
    "double": "2B",
    "triple": "3B",
    "sac_fly": "SF",
    "sac_bunt": "SAC",
    "field_error": "E",
    "fielders_choice": "FC",
    "walk": "BB",
    "intent_walk": "IBB",
    "hit_by_pitch": "HBP",
    "wild_pitch": "WP",
    "passed_ball": "PB",
    "balk": "BK",
    "groundout": "GO",
    "force_out": "FO",
    "field_out": "OUT",
}


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalized_event_key(value: Any) -> str:
    return str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")


def _event_code(play: dict[str, Any]) -> str:
    result = play.get("result", {}) or {}
    event_type = _normalized_event_key(result.get("eventType"))
    if event_type in EVENT_CODES:
        return EVENT_CODES[event_type]
    event = str(result.get("event") or "").strip()
    event_key = _normalized_event_key(event)
    if event_key in EVENT_CODES:
        return EVENT_CODES[event_key]
    return event or event_type.upper() or "RUN"


def _scorer_names(play: dict[str, Any]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for runner in play.get("runners", []) or []:
        if not isinstance(runner, dict):
            continue
        movement = runner.get("movement", {}) or {}
        details = runner.get("details", {}) or {}
        scored = str(movement.get("end") or "").casefold() == "score" or bool(
            details.get("isScoringEvent")
        )
        if not scored:
            continue
        person = details.get("runner", {}) or {}
        name = str(person.get("fullName") or "").strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _runner_rbi_count(play: dict[str, Any]) -> int:
    count = 0
    for runner in play.get("runners", []) or []:
        if not isinstance(runner, dict):
            continue
        details = runner.get("details", {}) or {}
        if details.get("rbi") is True:
            count += 1
    return count


def extract_scoring_plays(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """MLB live feed에서 실제 득점이 발생한 플레이를 시간순으로 정리한다."""
    plays = (((payload.get("liveData", {}) or {}).get("plays", {}) or {}).get("allPlays", []) or [])
    rows: list[dict[str, Any]] = []
    previous_away = 0
    previous_home = 0

    for play in plays:
        if not isinstance(play, dict):
            continue
        result = play.get("result", {}) or {}
        away_score = _safe_int(result.get("awayScore"))
        home_score = _safe_int(result.get("homeScore"))
        away_delta = max((away_score if away_score is not None else previous_away) - previous_away, 0)
        home_delta = max((home_score if home_score is not None else previous_home) - previous_home, 0)

        scorers = _scorer_names(play)
        rbi = _safe_int(result.get("rbi"))
        if rbi is None:
            runner_rbi = _runner_rbi_count(play)
            rbi = runner_rbi if runner_rbi else None

        if not scorers and not away_delta and not home_delta and not (rbi and rbi > 0):
            if away_score is not None:
                previous_away = away_score
            if home_score is not None:
                previous_home = home_score
            continue

        about = play.get("about", {}) or {}
        matchup = play.get("matchup", {}) or {}
        batter = matchup.get("batter", {}) or {}
        inning = _safe_int(about.get("inning"))
        half = str(about.get("halfInning") or "").casefold()
        if inning is None:
            inning_text = "—"
        elif half == "top":
            inning_text = f"{inning}회초"
        elif half == "bottom":
            inning_text = f"{inning}회말"
        else:
            inning_text = f"{inning}회"

        rows.append(
            {
                "inning": inning_text,
                "batter": str(batter.get("fullName") or "—"),
                "event": _event_code(play),
                "rbi": rbi,
                "scorers": scorers,
                "description": str(result.get("description") or ""),
                "runs": max(len(scorers), away_delta, home_delta),
            }
        )

        if away_score is not None:
            previous_away = away_score
        if home_score is not None:
            previous_home = home_score

    return rows


def install_gameday_enhancements() -> None:
    """라인스코어 아래에 득점자·득점 방식·타점 설명을 추가한다."""
    from PyQt6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem

    from services.mlb_api import MLBApiService
    from ui.game_view import GameView

    if getattr(MLBApiService, "_gameday_scoring_patch_installed", False):
        return

    original_parse_live_game = MLBApiService._parse_live_game
    original_game_view_init = GameView.__init__
    original_set_game = GameView.set_game

    def parse_live_game_with_scoring(self: MLBApiService, payload: dict[str, Any]):
        detail = original_parse_live_game(self, payload)
        try:
            detail.raw["_dugout_scoring_plays"] = extract_scoring_plays(payload)
        except Exception:
            detail.raw["_dugout_scoring_plays"] = []
        return detail

    def init_game_view_with_scoring(self: GameView) -> None:
        original_game_view_init(self)
        score_box = self.linescore.parentWidget()
        score_layout = score_box.layout() if score_box is not None else None
        if score_layout is None:
            return

        self.scoring_title = QLabel("득점 플레이")
        self.scoring_title.setObjectName("subtitle")
        score_layout.addWidget(self.scoring_title)

        self.scoring_table = QTableWidget(0, 6)
        self.scoring_table.setHorizontalHeaderLabels(
            ["이닝", "타자", "득점 방식", "타점", "득점자", "설명"]
        )
        self.scoring_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.scoring_table.setAlternatingRowColors(True)
        self.scoring_table.setWordWrap(True)
        self.scoring_table.setMaximumHeight(230)
        score_layout.addWidget(self.scoring_table)

        self.scoring_empty = QLabel("아직 득점 플레이가 없습니다.")
        self.scoring_empty.setObjectName("subtitle")
        score_layout.addWidget(self.scoring_empty)

    def fill_scoring_table(self: GameView, detail: Any) -> None:
        if not hasattr(self, "scoring_table"):
            return
        rows = detail.raw.get("_dugout_scoring_plays", []) if isinstance(detail.raw, dict) else []
        rows = rows if isinstance(rows, list) else []
        self.scoring_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            row = row if isinstance(row, dict) else {}
            rbi = row.get("rbi")
            values = [
                str(row.get("inning") or "—"),
                str(row.get("batter") or "—"),
                str(row.get("event") or "RUN"),
                "—" if rbi is None else f"{int(rbi)} RBI",
                ", ".join(str(name) for name in row.get("scorers", []) if name) or "—",
                str(row.get("description") or "—"),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                self.scoring_table.setItem(row_index, col, item)
        self.scoring_table.resizeColumnsToContents()
        has_rows = bool(rows)
        self.scoring_table.setVisible(has_rows)
        self.scoring_title.setVisible(has_rows)
        self.scoring_empty.setVisible(not has_rows)

    def set_game_with_scoring(self: GameView, detail: Any) -> None:
        original_set_game(self, detail)
        fill_scoring_table(self, detail)

    MLBApiService._parse_live_game = parse_live_game_with_scoring  # type: ignore[method-assign]
    GameView.__init__ = init_game_view_with_scoring  # type: ignore[method-assign]
    GameView.set_game = set_game_with_scoring  # type: ignore[method-assign]
    GameView._fill_scoring_table = fill_scoring_table  # type: ignore[attr-defined]
    MLBApiService._gameday_scoring_patch_installed = True  # type: ignore[attr-defined]
