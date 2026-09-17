from __future__ import annotations

from typing import Any

EVENT_CODES = {
    "home_run": "HR",
    "single": "1B",
    "double": "2B",
    "triple": "3B",
    "sac_fly": "SF",
    "sacrifice_fly": "SF",
    "sac_bunt": "SAC",
    "sacrifice_bunt": "SAC",
    "walk": "BB",
    "intent_walk": "IBB",
    "hit_by_pitch": "HBP",
    "field_error": "E",
    "fielders_choice": "FC",
    "fielders_choice_out": "FC",
    "wild_pitch": "WP",
    "passed_ball": "PB",
    "balk": "BK",
    "groundout": "GO",
    "force_out": "GO",
    "double_play": "DP",
    "grounded_into_double_play": "GIDP",
}


def _event_code(result: dict[str, Any]) -> str:
    event_type = str(result.get("eventType") or "").strip().lower()
    if event_type in EVENT_CODES:
        return EVENT_CODES[event_type]
    event = str(result.get("event") or "").strip()
    return event or "RUN"


def _scoring_runners(play: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for runner in play.get("runners", []) or []:
        if not isinstance(runner, dict):
            continue
        movement = runner.get("movement", {}) or {}
        if str(movement.get("end") or "").lower() != "score":
            continue
        details = runner.get("details", {}) or {}
        person = details.get("runner", {}) or {}
        name = str(person.get("fullName") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def extract_scoring_plays(detail: Any) -> list[dict[str, Any]]:
    raw = getattr(detail, "raw", {}) or {}
    live_data = raw.get("liveData", {}) if isinstance(raw, dict) else {}
    plays = (live_data.get("plays", {}) or {}).get("allPlays", []) or []
    rows: list[dict[str, Any]] = []

    for play in plays:
        if not isinstance(play, dict):
            continue
        result = play.get("result", {}) or {}
        about = play.get("about", {}) or {}
        scorers = _scoring_runners(play)
        try:
            rbi = int(result.get("rbi") or 0)
        except (TypeError, ValueError):
            rbi = 0
        is_scoring = bool(about.get("isScoringPlay")) or bool(scorers) or rbi > 0
        if not is_scoring:
            continue

        matchup = play.get("matchup", {}) or {}
        batter = matchup.get("batter", {}) or {}
        batter_name = str(batter.get("fullName") or "").strip()
        code = _event_code(result)
        if not scorers and code == "HR" and batter_name:
            scorers = [batter_name]

        inning = about.get("inning")
        half = str(about.get("halfInning") or "").lower()
        if inning:
            inning_text = f"{inning}회{'초' if half == 'top' else '말' if half == 'bottom' else ''}"
        else:
            inning_text = "—"

        description = str(result.get("description") or "").strip()
        rows.append(
            {
                "inning": inning_text,
                "scorers": ", ".join(scorers) if scorers else (batter_name or "—"),
                "play": code,
                "rbi": rbi,
                "batter": batter_name,
                "description": description,
            }
        )
    return rows


def install_live_scoring_support() -> None:
    """라인스코어 아래에 득점자, 득점 유형, 타점 설명을 표시한다."""
    from PyQt6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem

    from ui.game_view import GameView

    if getattr(GameView, "_live_scoring_patch_installed", False):
        return

    original_init = GameView.__init__
    original_set_game = GameView.set_game

    def init_with_scoring(self: GameView) -> None:
        original_init(self)
        score_box = self.linescore.parentWidget()
        score_layout = score_box.layout() if score_box is not None else None
        if score_layout is None:
            return
        title = QLabel("득점 플레이")
        title.setObjectName("subtitle")
        score_layout.addWidget(title)
        self.scoring_table = QTableWidget(0, 5)
        self.scoring_table.setHorizontalHeaderLabels(
            ["이닝", "득점자", "득점 유형", "타점", "설명"]
        )
        self.scoring_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.scoring_table.setAlternatingRowColors(True)
        self.scoring_table.setMinimumHeight(150)
        score_layout.addWidget(self.scoring_table)

    def set_game_with_scoring(self: GameView, detail: Any) -> None:
        original_set_game(self, detail)
        table = getattr(self, "scoring_table", None)
        if table is None:
            return
        rows = extract_scoring_plays(detail)
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                str(row.get("inning") or "—"),
                str(row.get("scorers") or "—"),
                str(row.get("play") or "RUN"),
                str(row.get("rbi") if row.get("rbi") is not None else "—"),
                str(row.get("description") or "—"),
            ]
            for col, value in enumerate(values):
                table.setItem(row_index, col, QTableWidgetItem(value))
        table.resizeColumnsToContents()
        if table.columnCount() >= 5:
            table.setColumnWidth(4, max(table.columnWidth(4), 420))

    GameView.__init__ = init_with_scoring  # type: ignore[method-assign]
    GameView.set_game = set_game_with_scoring  # type: ignore[method-assign]
    GameView._live_scoring_patch_installed = True  # type: ignore[attr-defined]
