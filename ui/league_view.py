from __future__ import annotations

from config.i18n import tr, tr_list

from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class LeagueView(QWidget):
    refresh_requested = pyqtSignal()
    team_selected = pyqtSignal(int)

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.refresh_button = QPushButton(tr("Refresh Standings"))
        self.refresh_button.clicked.connect(self.refresh_requested)
        controls.addWidget(self.refresh_button)
        controls.addStretch()
        root.addLayout(controls)

        self.tabs = QTabWidget()
        self.standings_table = self._table(
            ["Team", "W", "L", "Pct", "GB", "Division", "Div Rank", "WC Rank"]
        )
        self.wildcard_table = self._table(
            ["Team", "W", "L", "Pct", "GB", "League", "WC Rank"]
        )
        self.standings_table.cellDoubleClicked.connect(self._standing_double_click)
        self.tabs.addTab(self.standings_table, tr("Standings"))
        self.league_stats_table = self._table(
            ["Team", "R", "HR", "AVG", "OBP", "SLG", "OPS", "ERA", "WHIP", "SO"]
        )
        self.tabs.addTab(self.wildcard_table, tr("Wild Card"))
        self.tabs.addTab(self.league_stats_table, tr("League Stats"))
        root.addWidget(self.tabs, 1)

        team_box = QGroupBox(tr("Team Stats"))
        team_layout = QVBoxLayout(team_box)
        self.team_stats_label = QLabel(tr("Double-click a team in the standings."))
        self.team_stats_label.setWordWrap(True)
        team_layout.addWidget(self.team_stats_label)
        root.addWidget(team_box)
        self._standings: list[dict[str, Any]] = []

    @staticmethod
    def _table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(tr_list(headers))
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        return table

    def set_standings(self, rows: list[dict[str, Any]]) -> None:
        self._standings = rows
        self.standings_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [
                row.get("team"), row.get("wins"), row.get("losses"), row.get("pct"),
                row.get("games_back"), row.get("division"), row.get("division_rank"), row.get("wild_card_rank")
            ]
            for c, value in enumerate(values):
                self.standings_table.setItem(r, c, QTableWidgetItem(tr(str(value or "—"))))
        self.standings_table.resizeColumnsToContents()

        wc = [row for row in rows if row.get("wild_card_rank")]
        wc.sort(key=lambda row: (row.get("league", ""), self._rank(row.get("wild_card_rank"))))
        self.wildcard_table.setRowCount(len(wc))
        for r, row in enumerate(wc):
            values = [
                row.get("team"), row.get("wins"), row.get("losses"), row.get("pct"),
                row.get("games_back"), row.get("league"), row.get("wild_card_rank")
            ]
            for c, value in enumerate(values):
                self.wildcard_table.setItem(r, c, QTableWidgetItem(tr(str(value or "—"))))
        self.wildcard_table.resizeColumnsToContents()

    def set_league_stats(self, rows: list[dict[str, Any]]) -> None:
        self.league_stats_table.setRowCount(len(rows))
        keys = ["team", "R", "HR", "AVG", "OBP", "SLG", "OPS", "ERA", "WHIP", "SO"]
        for r, row in enumerate(rows):
            for c, key in enumerate(keys):
                value = row.get(key)
                self.league_stats_table.setItem(r, c, QTableWidgetItem(tr(str(value if value is not None else "—"))))
        self.league_stats_table.resizeColumnsToContents()

    def set_team_stats(self, stats: dict[str, Any]) -> None:
        lines: list[str] = []
        for group, data in stats.items():
            if not isinstance(data, dict):
                continue
            selected = []
            for key in ("gamesPlayed", "runs", "homeRuns", "avg", "obp", "slg", "ops", "era", "whip", "strikeOuts"):
                if key in data:
                    selected.append(f"{key}: {data[key]}")
            lines.append(f"{group.title()}: " + "  |  ".join(selected))
        self.team_stats_label.setText(tr("\n".join(lines) if lines else "No team stats returned."))

    def _standing_double_click(self, row: int, _column: int) -> None:
        if 0 <= row < len(self._standings):
            team_id = int(self._standings[row].get("team_id", 0))
            if team_id:
                self.team_selected.emit(team_id)

    @staticmethod
    def _rank(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 999
