from __future__ import annotations

from config.i18n import tr

from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from models.game import GameDetail, LineupPlayer


class LineupView(QWidget):
    player_clicked = pyqtSignal(int)

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self.columns = QHBoxLayout(content)
        self.away_box = QGroupBox(tr("Away Lineup"))
        self.home_box = QGroupBox(tr("Home Lineup"))
        self.away_layout = QVBoxLayout(self.away_box)
        self.home_layout = QVBoxLayout(self.home_box)
        self.columns.addWidget(self.away_box)
        self.columns.addWidget(self.home_box)
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def set_game(self, detail: GameDetail) -> None:
        self.away_box.setTitle(tr(f"{detail.away.name} Lineup"))
        self.home_box.setTitle(tr(f"{detail.home.name} Lineup"))
        self._fill(self.away_layout, detail.away_lineup, detail.away_pitchers)
        self._fill(self.home_layout, detail.home_lineup, detail.home_pitchers)

    def _fill(
        self,
        layout: QVBoxLayout,
        players: list[LineupPlayer],
        pitchers: list[LineupPlayer],
    ) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        batting_label = QLabel(tr("Batting Order"))
        batting_label.setObjectName("subtitle")
        layout.addWidget(batting_label)
        if not players:
            label = QLabel(tr("Lineup has not been posted yet."))
            label.setObjectName("subtitle")
            layout.addWidget(label)
        for index, player in enumerate(players, start=1):
            order = player.batting_order or index
            text = f"{order}. {player.name}   {player.position}".strip()
            button = QPushButton(tr(text))
            button.clicked.connect(
                lambda _checked=False, pid=player.id: self.player_clicked.emit(pid)
            )
            layout.addWidget(button)

        pitching_label = QLabel(tr("Pitchers Used"))
        pitching_label.setObjectName("subtitle")
        layout.addWidget(pitching_label)
        if not pitchers:
            label = QLabel(tr("No pitcher has appeared in the box score yet."))
            label.setObjectName("subtitle")
            layout.addWidget(label)
        for index, pitcher in enumerate(pitchers, start=1):
            line = self._pitching_line(pitcher.game_stats)
            prefix = "SP" if index == 1 else f"RP {index - 1}"
            text = f"{prefix}. {pitcher.name}"
            if line:
                text += f"   |   {line}"
            button = QPushButton(tr(text))
            button.clicked.connect(
                lambda _checked=False, pid=pitcher.id: self.player_clicked.emit(pid)
            )
            layout.addWidget(button)
        layout.addStretch()

    @staticmethod
    def _pitching_line(stats: dict[str, Any]) -> str:
        if not stats:
            return ""
        fields = [
            ("IP", stats.get("inningsPitched")),
            ("H", stats.get("hits")),
            ("R", stats.get("runs")),
            ("ER", stats.get("earnedRuns")),
            ("BB", stats.get("baseOnBalls")),
            ("K", stats.get("strikeOuts")),
        ]
        return "  ".join(f"{label} {value}" for label, value in fields if value is not None)
