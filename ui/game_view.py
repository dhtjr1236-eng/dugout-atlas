from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.game import GameDetail
from ui.widgets.svg_logo import SvgLogoLabel


class GameView(QWidget):
    player_clicked = pyqtSignal(int)

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)

        header = QFrame()
        header.setObjectName("panel")
        header_layout = QHBoxLayout(header)
        self.away_logo = SvgLogoLabel(54)
        self.home_logo = SvgLogoLabel(54)
        self.away_label = QLabel("Away")
        self.home_label = QLabel("Home")
        self.away_label.setObjectName("title")
        self.home_label.setObjectName("title")
        self.score_label = QLabel("–")
        self.score_label.setObjectName("title")
        header_layout.addWidget(self.away_logo)
        header_layout.addWidget(self.away_label)
        header_layout.addStretch()
        header_layout.addWidget(self.score_label)
        header_layout.addStretch()
        header_layout.addWidget(self.home_label)
        header_layout.addWidget(self.home_logo)
        root.addWidget(header)

        state_box = QGroupBox("Live Game State")
        state_layout = QGridLayout(state_box)
        self.status_label = QLabel("Select a game")
        self.inning_label = QLabel("—")
        self.count_label = QLabel("0-0")
        self.outs_label = QLabel("0")
        self.bases_label = QLabel("1B ○   2B ○   3B ○")
        state_layout.addWidget(QLabel("Status"), 0, 0)
        state_layout.addWidget(self.status_label, 0, 1)
        state_layout.addWidget(QLabel("Inning"), 0, 2)
        state_layout.addWidget(self.inning_label, 0, 3)
        state_layout.addWidget(QLabel("Count"), 1, 0)
        state_layout.addWidget(self.count_label, 1, 1)
        state_layout.addWidget(QLabel("Outs"), 1, 2)
        state_layout.addWidget(self.outs_label, 1, 3)
        state_layout.addWidget(QLabel("Runners"), 2, 0)
        state_layout.addWidget(self.bases_label, 2, 1, 1, 3)
        root.addWidget(state_box)

        matchup_box = QGroupBox("Current Matchup")
        matchup_layout = QGridLayout(matchup_box)
        self.batter_button = QPushButton("—")
        self.pitcher_button = QPushButton("—")
        self.batter_button.clicked.connect(self._emit_batter)
        self.pitcher_button.clicked.connect(self._emit_pitcher)
        self._batter_id: int | None = None
        self._pitcher_id: int | None = None
        matchup_layout.addWidget(QLabel("Batter"), 0, 0)
        matchup_layout.addWidget(self.batter_button, 0, 1)
        matchup_layout.addWidget(QLabel("Pitcher"), 1, 0)
        matchup_layout.addWidget(self.pitcher_button, 1, 1)
        root.addWidget(matchup_box)

        play_box = QGroupBox("Recent Play")
        play_layout = QVBoxLayout(play_box)
        self.play_label = QLabel("—")
        self.play_label.setWordWrap(True)
        play_layout.addWidget(self.play_label)
        root.addWidget(play_box)

        score_box = QGroupBox("Linescore")
        score_layout = QVBoxLayout(score_box)
        self.linescore = QTableWidget(2, 1)
        self.linescore.setVerticalHeaderLabels(["Away", "Home"])
        self.linescore.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        score_layout.addWidget(self.linescore)
        root.addWidget(score_box, 1)

    def set_game(self, detail: GameDetail) -> None:
        self.away_label.setText(detail.away.abbreviation or detail.away.name)
        self.home_label.setText(detail.home.abbreviation or detail.home.name)
        self.away_logo.set_logo(detail.away.logo_path)
        self.home_logo.set_logo(detail.home.logo_path)
        away_score = detail.away.score if detail.away.score is not None else 0
        home_score = detail.home.score if detail.home.score is not None else 0
        self.score_label.setText(f"{away_score}  –  {home_score}")
        self.status_label.setText(detail.status)
        inning = f"{detail.inning_state} {detail.inning}" if detail.inning else "—"
        self.inning_label.setText(inning.strip())
        self.count_label.setText(f"{detail.balls}-{detail.strikes}")
        self.outs_label.setText(str(detail.outs))
        self.bases_label.setText(
            "   ".join(
                [
                    f"1B {'●' if detail.on_first else '○'}",
                    f"2B {'●' if detail.on_second else '○'}",
                    f"3B {'●' if detail.on_third else '○'}",
                ]
            )
        )

        self._batter_id = detail.batter.id if detail.batter else None
        self._pitcher_id = detail.pitcher.id if detail.pitcher else None
        self.batter_button.setText(detail.batter.name if detail.batter else "—")
        self.pitcher_button.setText(detail.pitcher.name if detail.pitcher else "—")
        self.play_label.setText(detail.recent_play or "—")
        self._set_linescore(detail)

    def _set_linescore(self, detail: GameDetail) -> None:
        innings = detail.linescore
        extra_cols = 3
        self.linescore.setColumnCount(len(innings) + extra_cols)
        headers = [str(item.get("num", index + 1)) for index, item in enumerate(innings)]
        headers.extend(["R", "H", "E"])
        self.linescore.setHorizontalHeaderLabels(headers)

        away_runs = 0
        home_runs = 0
        for col, inning in enumerate(innings):
            away = inning.get("away")
            home = inning.get("home")
            away_runs += int(away or 0)
            home_runs += int(home or 0)
            self.linescore.setItem(0, col, QTableWidgetItem("" if away is None else str(away)))
            self.linescore.setItem(1, col, QTableWidgetItem("" if home is None else str(home)))
        run_col = len(innings)
        self.linescore.setItem(0, run_col, QTableWidgetItem(str(detail.away.score if detail.away.score is not None else away_runs)))
        self.linescore.setItem(1, run_col, QTableWidgetItem(str(detail.home.score if detail.home.score is not None else home_runs)))
        self.linescore.setItem(0, run_col + 1, QTableWidgetItem(str(detail.away_hits) if detail.away_hits is not None else "—"))
        self.linescore.setItem(1, run_col + 1, QTableWidgetItem(str(detail.home_hits) if detail.home_hits is not None else "—"))
        self.linescore.setItem(0, run_col + 2, QTableWidgetItem(str(detail.away_errors) if detail.away_errors is not None else "—"))
        self.linescore.setItem(1, run_col + 2, QTableWidgetItem(str(detail.home_errors) if detail.home_errors is not None else "—"))
        self.linescore.resizeColumnsToContents()

    def _emit_batter(self) -> None:
        if self._batter_id:
            self.player_clicked.emit(self._batter_id)

    def _emit_pitcher(self) -> None:
        if self._pitcher_id:
            self.player_clicked.emit(self._pitcher_id)
