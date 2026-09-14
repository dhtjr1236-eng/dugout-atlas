from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QStringListModel, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCompleter,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.player import PlayerBundle


class CompareView(QWidget):
    """Side-by-side player comparison with two independent autocomplete searches."""

    search_requested = pyqtSignal(int, str)
    player_selected = pyqtSignal(int, int)

    def __init__(self) -> None:
        super().__init__()
        self._bundles: dict[int, PlayerBundle | None] = {0: None, 1: None}
        self._search_maps: dict[int, dict[str, int]] = {0: {}, 1: {}}
        self._search_models: dict[int, QStringListModel] = {}
        self._completers: dict[int, QCompleter] = {}
        self._timers: dict[int, QTimer] = {}
        self._searches: dict[int, QLineEdit] = {}
        self._name_labels: dict[int, QLabel] = {}
        self._profile_labels: dict[int, QLabel] = {}

        root = QVBoxLayout(self)
        title = QLabel("Compare Players")
        title.setObjectName("title")
        root.addWidget(title)
        subtitle = QLabel(
            "Type two player names and select each autocomplete result. "
            "Hitters and pitchers are compared using the metrics available for their role."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        search_row = QHBoxLayout()
        for slot, caption in ((0, "Player A"), (1, "Player B")):
            pane = QWidget()
            pane_layout = QVBoxLayout(pane)
            pane_layout.setContentsMargins(0, 0, 0, 0)
            pane_layout.addWidget(QLabel(caption))

            search = QLineEdit()
            search.setPlaceholderText(f"Search {caption} (e.g. Judge)")
            search.setMinimumWidth(300)
            model = QStringListModel(self)
            completer = QCompleter(model, self)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            search.setCompleter(completer)
            pane_layout.addWidget(search)

            name = QLabel("No player selected")
            name.setObjectName("title")
            profile = QLabel("—")
            profile.setObjectName("subtitle")
            pane_layout.addWidget(name)
            pane_layout.addWidget(profile)
            search_row.addWidget(pane, 1)

            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(350)
            timer.timeout.connect(lambda s=slot: self._emit_search(s))
            search.textChanged.connect(lambda _text, s=slot: self._timers[s].start())
            search.returnPressed.connect(lambda s=slot: self._on_search_enter(s))
            completer.activated[str].connect(
                lambda label, s=slot: self._on_completion(s, label)
            )

            self._searches[slot] = search
            self._search_models[slot] = model
            self._completers[slot] = completer
            self._timers[slot] = timer
            self._name_labels[slot] = name
            self._profile_labels[slot] = profile

        root.addLayout(search_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Metric", "Player A", "Player B"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        root.addWidget(self.table, 1)
        self._render()

    def current_query(self, slot: int) -> str:
        search = self._searches.get(slot)
        return search.text().strip() if search is not None else ""

    def update_search_results(self, slot: int, rows: list[dict[str, object]]) -> None:
        if slot not in self._search_maps:
            return
        mapping: dict[str, int] = {}
        labels: list[str] = []
        for row in rows:
            name = str(row.get("name", ""))
            if not name:
                continue
            team = str(row.get("team", ""))
            position = str(row.get("position", ""))
            label = name
            if team or position:
                label = f"{name} — {team} {position}".strip()
            player_id = int(row.get("id", 0) or 0)
            if player_id:
                mapping[label] = player_id
                labels.append(label)
        self._search_maps[slot] = mapping
        self._search_models[slot].setStringList(labels)
        if labels and self._searches[slot].hasFocus():
            self._completers[slot].complete()

    def set_loading(self, slot: int, player_id: int) -> None:
        if slot not in self._name_labels:
            return
        self._name_labels[slot].setText(f"Loading player {player_id}…")
        self._profile_labels[slot].setText("Collecting MLB / FanGraphs / B-Ref / Statcast…")

    def set_player(self, slot: int, bundle: PlayerBundle) -> None:
        if slot not in self._bundles:
            return
        self._bundles[slot] = bundle
        profile = bundle.profile
        self._name_labels[slot].setText(profile.full_name)
        role = "Pitcher" if profile.is_pitcher else "Hitter"
        self._profile_labels[slot].setText(
            f"{profile.team or '—'} | {profile.position or '—'} | {role} | Age {profile.age or '—'}"
        )
        self._render()

    def _emit_search(self, slot: int) -> None:
        text = self.current_query(slot)
        if len(text) >= 2:
            self.search_requested.emit(slot, text)
        else:
            self.update_search_results(slot, [])

    def _on_completion(self, slot: int, label: str) -> None:
        player_id = self._search_maps.get(slot, {}).get(label)
        if player_id:
            self.player_selected.emit(slot, player_id)

    def _on_search_enter(self, slot: int) -> None:
        text = self.current_query(slot).casefold()
        for label, player_id in self._search_maps.get(slot, {}).items():
            if label.casefold().startswith(text):
                self.player_selected.emit(slot, player_id)
                return

    def _render(self) -> None:
        left = self._bundles[0]
        right = self._bundles[1]
        rows = self._metric_rows(left, right)
        self.table.setRowCount(len(rows))
        left_name = left.profile.full_name if left is not None else "Player A"
        right_name = right.profile.full_name if right is not None else "Player B"
        self.table.setHorizontalHeaderLabels(["Metric", left_name, right_name])

        for row_index, (label, left_value, right_value) in enumerate(rows):
            self.table.setItem(row_index, 0, QTableWidgetItem(label))
            self.table.setItem(row_index, 1, QTableWidgetItem(self._format(left_value)))
            self.table.setItem(row_index, 2, QTableWidgetItem(self._format(right_value)))
        self.table.resizeColumnsToContents()

    def _metric_rows(
        self, left: PlayerBundle | None, right: PlayerBundle | None
    ) -> list[tuple[str, Any, Any]]:
        labels = self._labels_for(left, right)
        return [
            (
                label,
                self._metric_value(left, label),
                self._metric_value(right, label),
            )
            for label in labels
        ]

    @staticmethod
    def _labels_for(
        left: PlayerBundle | None, right: PlayerBundle | None
    ) -> list[str]:
        bundles = [bundle for bundle in (left, right) if bundle is not None]
        if not bundles:
            return ["Select two players to compare"]
        pitchers = [bundle.profile.is_pitcher for bundle in bundles]
        if pitchers and all(pitchers):
            return [
                "ERA",
                "WHIP",
                "FIP",
                "xFIP",
                "K%",
                "BB%",
                "fWAR",
                "bWAR",
                "ERA+",
                "xERA",
                "xBA",
                "xSLG",
                "xwOBA",
                "Whiff %",
                "Chase %",
                "Avg EV Allowed",
            ]
        if pitchers and not any(pitchers):
            return [
                "AVG",
                "OBP",
                "SLG",
                "OPS",
                "HR",
                "RBI",
                "SB",
                "PA",
                "fWAR",
                "bWAR",
                "wRC+",
                "OPS+",
                "ISO",
                "BABIP",
                "BB%",
                "K%",
                "wOBA",
                "Avg EV",
                "Max EV",
                "Hard Hit %",
                "Barrel %",
                "xBA",
                "xSLG",
                "xwOBA",
                "OAA",
                "Runs Prevented",
            ]
        return ["fWAR", "bWAR", "BB%", "K%", "xBA", "xSLG", "xwOBA"]

    @classmethod
    def _metric_value(cls, bundle: PlayerBundle | None, label: str) -> Any:
        if bundle is None:
            return None
        basic = bundle.basic
        fg = bundle.fangraphs
        bref = bundle.bref
        sc = bundle.statcast
        defense = bundle.defense
        profile = bundle.profile

        if profile.is_pitcher:
            batters_faced = cls._number(basic.get("battersFaced"))
            strikeouts = cls._number(basic.get("strikeOuts"))
            walks = cls._number(basic.get("baseOnBalls"))
            mapping = {
                "ERA": basic.get("era", fg.get("ERA")),
                "WHIP": basic.get("whip", fg.get("WHIP")),
                "FIP": fg.get("FIP"),
                "xFIP": fg.get("xFIP"),
                "K%": (strikeouts / batters_faced * 100) if batters_faced else fg.get("K%"),
                "BB%": (walks / batters_faced * 100) if batters_faced else fg.get("BB%"),
                "fWAR": fg.get("fWAR"),
                "bWAR": bref.get("bWAR"),
                "ERA+": bref.get("ERA+"),
                "xERA": sc.get("xERA"),
                "xBA": sc.get("xBA"),
                "xSLG": sc.get("xSLG"),
                "xwOBA": sc.get("xwOBA"),
                "Whiff %": sc.get("Whiff %"),
                "Chase %": sc.get("Chase %"),
                "Avg EV Allowed": sc.get("Average Exit Velocity Allowed"),
            }
            return mapping.get(label)

        mapping = {
            "AVG": basic.get("avg", fg.get("AVG")),
            "OBP": basic.get("obp", fg.get("OBP")),
            "SLG": basic.get("slg", fg.get("SLG")),
            "OPS": basic.get("ops", fg.get("OPS")),
            "HR": basic.get("homeRuns", fg.get("HR")),
            "RBI": basic.get("rbi", fg.get("RBI")),
            "SB": basic.get("stolenBases", fg.get("SB")),
            "PA": basic.get("plateAppearances", fg.get("PA")),
            "fWAR": fg.get("fWAR"),
            "bWAR": bref.get("bWAR"),
            "wRC+": fg.get("wRC+"),
            "OPS+": bref.get("OPS+"),
            "ISO": fg.get("ISO"),
            "BABIP": fg.get("BABIP"),
            "BB%": fg.get("BB%"),
            "K%": fg.get("K%"),
            "wOBA": fg.get("wOBA"),
            "Avg EV": sc.get("Average Exit Velocity"),
            "Max EV": sc.get("Max Exit Velocity"),
            "Hard Hit %": sc.get("Hard Hit %"),
            "Barrel %": sc.get("Barrel %"),
            "xBA": sc.get("xBA"),
            "xSLG": sc.get("xSLG"),
            "xwOBA": sc.get("xwOBA"),
            "OAA": defense.get("OAA"),
            "Runs Prevented": defense.get("Runs Prevented"),
        }
        return mapping.get(label)

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _format(value: Any) -> str:
        if value is None:
            return "—"
        if isinstance(value, float):
            if abs(value) < 1:
                return f"{value:.3f}"
            return f"{value:.2f}"
        return str(value)
