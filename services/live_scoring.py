from __future__ import annotations

from typing import Any

EVENT_LABELS = {
    "home_run": "HR",
    "triple": "3B",
    "double": "2B",
    "single": "1B",
    "sac_fly": "SF",
    "sac_bunt": "SAC",
    "field_out": "OUT",
    "force_out": "FC",
    "fielders_choice": "FC",
    "fielders_choice_out": "FC",
    "walk": "BB",
    "hit_by_pitch": "HBP",
    "wild_pitch": "WP",
    "passed_ball": "PB",
    "field_error": "E",
    "other_out": "OUT",
}


def _event_label(result: dict[str, Any]) -> str:
    event_type = str(result.get("eventType") or "").strip().lower()
    if event_type in EVENT_LABELS:
        return EVENT_LABELS[event_type]
    event = str(result.get("event") or "").strip()
    return event or event_type.replace("_", " ").upper() or "RUN"


def _scorers(play: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for runner in play.get("runners", []) or []:
        if not isinstance(runner, dict):
            continue
        movement = runner.get("movement", {}) or {}
        if str(movement.get("end") or "").lower() not in {"score", "home"}:
            continue
        details = runner.get("details", {}) or {}
        person = details.get("runner", {}) or {}
        name = str(person.get("fullName") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def extract_scoring_plays(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """MLB live feed에서 득점이 발생한 플레이를 시간순으로 추출한다."""
    plays_root = ((payload.get("liveData", {}) or {}).get("plays", {}) or {})
    rows: list[dict[str, Any]] = []
    previous_away = 0
    previous_home = 0

    for play in plays_root.get("allPlays", []) or []:
        if not isinstance(play, dict):
            continue
        result = play.get("result", {}) or {}
        about = play.get("about", {}) or {}
        matchup = play.get("matchup", {}) or {}
        try:
            away_score = int(result.get("awayScore", previous_away) or 0)
        except (TypeError, ValueError):
            away_score = previous_away
        try:
            home_score = int(result.get("homeScore", previous_home) or 0)
        except (TypeError, ValueError):
            home_score = previous_home

        away_delta = max(0, away_score - previous_away)
        home_delta = max(0, home_score - previous_home)
        runs_scored = away_delta + home_delta
        previous_away = away_score
        previous_home = home_score
        if runs_scored <= 0:
            continue

        batter = matchup.get("batter", {}) or {}
        try:
            rbi = int(result.get("rbi") or 0)
        except (TypeError, ValueError):
            rbi = 0
        inning = about.get("inning")
        half = str(about.get("halfInning") or "").strip().lower()
        half_label = "초" if half == "top" else "말" if half == "bottom" else half
        rows.append(
            {
                "inning": f"{inning}회 {half_label}" if inning else half_label or "—",
                "side": "away" if away_delta else "home",
                "scorers": _scorers(play),
                "batter": str(batter.get("fullName") or "").strip(),
                "event": _event_label(result),
                "rbi": rbi,
                "runs": runs_scored,
                "description": str(result.get("description") or "").strip(),
            }
        )
    return rows


def install_live_scoring_support() -> None:
    """Linescore 아래에 득점 플레이와 타점 설명 표를 추가한다."""
    from PyQt6.QtWidgets import QGroupBox, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout
    from services.mlb_api import MLBApiService
    from ui.game_view import GameView

    if getattr(MLBApiService, "_live_scoring_patch_installed", False):
        return

    original_parse = MLBApiService._parse_live_game
    original_init = GameView.__init__
    original_set_game = GameView.set_game

    def parse_with_scoring(self: MLBApiService, payload: dict[str, Any]):
        detail = original_parse(self, payload)
        detail.raw["_dugout_scoring_plays"] = extract_scoring_plays(payload)
        return detail

    def init_with_scoring(self: GameView) -> None:
        original_init(self)
        self.scoring_box = QGroupBox("득점 플레이 / 타점")
        scoring_layout = QVBoxLayout(self.scoring_box)
        self.scoring_note = QLabel("득점이 발생한 플레이의 득점자, 타자 이벤트, 타점을 표시합니다.")
        self.scoring_note.setWordWrap(True)
        self.scoring_table = QTableWidget(0, 5)
        self.scoring_table.setHorizontalHeaderLabels(["이닝", "득점자", "타자 / 결과", "타점", "설명"])
        self.scoring_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.scoring_table.setAlternatingRowColors(True)
        scoring_layout.addWidget(self.scoring_note)
        scoring_layout.addWidget(self.scoring_table)

        root = self.layout()
        score_box = self.linescore.parentWidget()
        index = root.indexOf(score_box) if root is not None else -1
        if root is not None:
            root.insertWidget(index + 1 if index >= 0 else root.count(), self.scoring_box)

    def set_game_with_scoring(self: GameView, detail: Any) -> None:
        original_set_game(self, detail)
        rows = detail.raw.get("_dugout_scoring_plays", []) if isinstance(detail.raw, dict) else []
        rows = rows if isinstance(rows, list) else []
        self.scoring_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            row = row if isinstance(row, dict) else {}
            scorers = ", ".join(str(name) for name in row.get("scorers", []) if name) or "—"
            batter = str(row.get("batter") or "—")
            event = str(row.get("event") or "RUN")
            rbi = row.get("rbi")
            values = [
                str(row.get("inning") or "—"),
                scorers,
                f"{batter} · {event}",
                f"{rbi} RBI" if isinstance(rbi, int) and rbi > 0 else "—",
                str(row.get("description") or "—"),
            ]
            for col, value in enumerate(values):
                self.scoring_table.setItem(row_index, col, QTableWidgetItem(value))
        self.scoring_table.resizeColumnsToContents()
        self.scoring_note.setText(
            f"득점 플레이 {len(rows)}개 · MLB Live Feed 기준" if rows else "아직 득점 플레이가 없습니다."
        )

    MLBApiService._parse_live_game = parse_with_scoring  # type: ignore[method-assign]
    GameView.__init__ = init_with_scoring  # type: ignore[method-assign]
    GameView.set_game = set_game_with_scoring  # type: ignore[method-assign]
    MLBApiService._live_scoring_patch_installed = True  # type: ignore[attr-defined]
