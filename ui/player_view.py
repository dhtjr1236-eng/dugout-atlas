from __future__ import annotations

import html
from typing import Any

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from charts.batter_charts import (
    barrel_percentage,
    exit_velocity_distribution,
    hard_hit_percentage,
    war_history,
    wrc_history,
)
from charts.pitcher_charts import pitch_usage, run_value, velocity_history, whiff_by_pitch
from models.player import PlayerBundle
from ui.widgets.metric_grid import MetricGrid


class PlayerView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.layout = QVBoxLayout(self.content)

        self.name_label = QLabel("Select a player")
        self.name_label.setObjectName("title")
        self.profile_label = QLabel("Search by name or click a lineup player.")
        self.profile_label.setObjectName("subtitle")
        self.layout.addWidget(self.name_label)
        self.layout.addWidget(self.profile_label)

        self.basic_box, self.basic_grid = self._metric_box("Basic Stats")
        self.advanced_box, self.advanced_grid = self._metric_box("FanGraphs / Baseball Reference")
        self.statcast_box, self.statcast_grid = self._metric_box("Statcast")
        self.defense_box, self.defense_grid = self._metric_box("Defense")

        self.pitch_box = QGroupBox("Pitch Arsenal")
        pitch_layout = QVBoxLayout(self.pitch_box)
        self.pitch_table = QTableWidget(0, 7)
        self.pitch_table.setHorizontalHeaderLabels(
            ["Pitch", "Usage %", "Avg Velo", "Max Velo", "Spin", "Run Value", "Whiff %"]
        )
        self.pitch_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        pitch_layout.addWidget(self.pitch_table)
        self.layout.addWidget(self.pitch_box)

        self.chart_tabs = QTabWidget()
        self.chart_tabs.setMinimumHeight(430)
        self.layout.addWidget(self.chart_tabs)

        self.source_box = QGroupBox("Data Sources")
        source_layout = QVBoxLayout(self.source_box)
        self.source_label = QLabel("")
        self.source_label.setWordWrap(True)
        self.source_label.setOpenExternalLinks(True)
        self.source_label.setTextFormat(self.source_label.textFormat())
        source_layout.addWidget(self.source_label)
        self.layout.addWidget(self.source_box)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setObjectName("subtitle")
        self.layout.addWidget(self.error_label)
        self.layout.addStretch()
        scroll.setWidget(self.content)
        root.addWidget(scroll)
        self.pitch_box.hide()
        self.defense_box.hide()

    def _metric_box(self, title: str) -> tuple[QGroupBox, MetricGrid]:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        grid = MetricGrid(columns=4)
        layout.addWidget(grid)
        self.layout.addWidget(box)
        return box, grid

    def set_loading(self, player_id: int) -> None:
        self.name_label.setText(f"Loading player {player_id}…")
        self.profile_label.setText("Collecting MLB, FanGraphs, Baseball Reference and Statcast data.")

    def set_bundle(self, bundle: PlayerBundle) -> None:
        profile = bundle.profile
        self.name_label.setText(profile.full_name)
        hand = f"Bats: {profile.bats or '—'}  |  Throws: {profile.throws or '—'}"
        self.profile_label.setText(
            f"{profile.team or '—'}  |  {profile.position or '—'}  |  Age {profile.age or '—'}  |  {hand}"
        )
        if profile.is_pitcher:
            self._show_pitcher(bundle)
        else:
            self._show_batter(bundle)
        self._show_sources(bundle)
        self.error_label.setText(
            "Some sources were unavailable: " + " | ".join(bundle.errors)
            if bundle.errors
            else ""
        )

    def _show_batter(self, bundle: PlayerBundle) -> None:
        basic = bundle.basic
        fg = bundle.fangraphs
        bref = bundle.bref
        sc = bundle.statcast
        defense = bundle.defense
        self.pitch_box.hide()
        self.defense_box.show()

        self.basic_grid.set_metrics(
            [
                ("AVG", basic.get("avg", fg.get("AVG")), False),
                ("OBP", basic.get("obp", fg.get("OBP")), False),
                ("SLG", basic.get("slg", fg.get("SLG")), False),
                ("OPS", basic.get("ops", fg.get("OPS")), False),
                ("HR", basic.get("homeRuns", fg.get("HR")), False),
                ("RBI", basic.get("rbi", fg.get("RBI")), False),
                ("SB", basic.get("stolenBases", fg.get("SB")), False),
                ("PA", basic.get("plateAppearances", fg.get("PA")), False),
            ]
        )
        self.advanced_grid.set_metrics(
            [
                ("fWAR", fg.get("fWAR"), False),
                ("bWAR", bref.get("bWAR"), False),
                ("wRC+", fg.get("wRC+"), False),
                ("OPS+", bref.get("OPS+"), False),
                ("ISO", fg.get("ISO"), False),
                ("BABIP", fg.get("BABIP"), False),
                ("BB%", fg.get("BB%"), True),
                ("K%", fg.get("K%"), True),
                ("wOBA", fg.get("wOBA"), False),
            ]
        )
        self.statcast_grid.set_metrics(
            [
                ("Avg EV", sc.get("Average Exit Velocity"), False),
                ("Max EV", sc.get("Max Exit Velocity"), False),
                ("Hard Hit %", sc.get("Hard Hit %"), True),
                ("Barrel %", sc.get("Barrel %"), True),
                ("Sweet Spot %", sc.get("Sweet Spot %"), True),
                ("xBA", sc.get("xBA"), False),
                ("xSLG", sc.get("xSLG"), False),
                ("xwOBA", sc.get("xwOBA"), False),
                ("Chase %", sc.get("Chase %"), True),
                ("Whiff %", sc.get("Whiff %"), True),
            ]
        )
        self.defense_grid.set_metrics(
            [
                ("OAA", defense.get("OAA"), False),
                ("Runs Prevented", defense.get("Runs Prevented"), False),
                ("Fielding Run Value", defense.get("Fielding Run Value"), False),
                ("Arm Value", defense.get("Arm Value"), False),
            ]
        )
        self._set_charts(
            [
                ("Exit Velocity", exit_velocity_distribution(sc)),
                ("Barrel %", barrel_percentage(sc)),
                ("Hard Hit %", hard_hit_percentage(sc)),
                ("WAR", war_history(bundle.history)),
                ("wRC+", wrc_history(bundle.history)),
            ]
        )

    def _show_pitcher(self, bundle: PlayerBundle) -> None:
        basic = bundle.basic
        fg = bundle.fangraphs
        bref = bundle.bref
        sc = bundle.statcast
        self.defense_box.hide()
        self.pitch_box.show()
        batters_faced = self._number(basic.get("battersFaced"))
        strikeouts = self._number(basic.get("strikeOuts"))
        walks = self._number(basic.get("baseOnBalls"))
        k_pct = (strikeouts / batters_faced * 100) if batters_faced else fg.get("K%")
        bb_pct = (walks / batters_faced * 100) if batters_faced else fg.get("BB%")
        self.basic_grid.set_metrics(
            [
                ("ERA", basic.get("era", fg.get("ERA")), False),
                ("FIP", fg.get("FIP"), False),
                ("xFIP", fg.get("xFIP"), False),
                ("WHIP", basic.get("whip", fg.get("WHIP")), False),
                ("K%", k_pct, True),
                ("BB%", bb_pct, True),
            ]
        )
        self.advanced_grid.set_metrics(
            [
                ("fWAR", fg.get("fWAR"), False),
                ("bWAR", bref.get("bWAR"), False),
                ("ERA+", bref.get("ERA+"), False),
            ]
        )
        self.statcast_grid.set_metrics(
            [
                ("xERA", sc.get("xERA"), False),
                ("xBA", sc.get("xBA"), False),
                ("xSLG", sc.get("xSLG"), False),
                ("xwOBA", sc.get("xwOBA"), False),
                ("Whiff %", sc.get("Whiff %"), True),
                ("Chase %", sc.get("Chase %"), True),
            ]
        )
        self._fill_pitch_table(bundle.pitch_table)
        self._set_charts(
            [
                ("Pitch Usage", pitch_usage(bundle.pitch_table)),
                ("Run Value", run_value(bundle.pitch_table)),
                ("Velocity", velocity_history(bundle.velocity_history)),
                ("Whiff %", whiff_by_pitch(bundle.pitch_table)),
            ]
        )

    def _fill_pitch_table(self, rows: list[dict[str, Any]]) -> None:
        self.pitch_table.setRowCount(len(rows))
        keys = ["pitch_type", "Usage %", "Avg Velocity", "Max Velocity", "Spin Rate", "Run Value", "Whiff %"]
        for row_index, row in enumerate(rows):
            for col, key in enumerate(keys):
                value = row.get(key)
                if value is None:
                    text = "—"
                elif isinstance(value, float):
                    text = f"{value:.1f}" if key in {"Usage %", "Avg Velocity", "Max Velocity", "Whiff %"} else f"{value:.2f}"
                else:
                    text = str(value)
                self.pitch_table.setItem(row_index, col, QTableWidgetItem(text))
        self.pitch_table.resizeColumnsToContents()

    def _set_charts(self, charts: list[tuple[str, Figure]]) -> None:
        while self.chart_tabs.count():
            widget = self.chart_tabs.widget(0)
            self.chart_tabs.removeTab(0)
            widget.deleteLater()
        for title, figure in charts:
            canvas = FigureCanvasQTAgg(figure)
            canvas.setMinimumHeight(360)
            holder = QWidget()
            holder.setMinimumHeight(390)
            layout = QVBoxLayout(holder)
            layout.addWidget(canvas)
            self.chart_tabs.addTab(holder, title)

    def _show_sources(self, bundle: PlayerBundle) -> None:
        entries: list[dict[str, Any]] = []
        rows: list[str] = []
        providers = (
            ("FanGraphs", bundle.fangraphs),
            ("Baseball-Reference", bundle.bref),
            ("Baseball Savant / Statcast", bundle.statcast),
            ("Baseball Savant Defense", bundle.defense),
        )
        for provider_name, container in providers:
            if not isinstance(container, dict):
                continue
            status = str(container.get("_status") or "").strip().lower()
            if status:
                label = {
                    "ok": "OK",
                    "partial": "PARTIAL",
                    "unavailable": "UNAVAILABLE",
                }.get(status, status.upper())
                rows.append(f"<b>{html.escape(provider_name)}</b>: {html.escape(label)}")
            one = container.get("_source")
            if isinstance(one, dict):
                entries.append(one)
            many = container.get("_sources")
            if isinstance(many, list):
                entries.extend(item for item in many if isinstance(item, dict))

        seen: set[tuple[str, str]] = set()
        for entry in entries:
            name = str(entry.get("name") or "Source")
            url = str(entry.get("url") or "")
            key = (name, url)
            if key in seen:
                continue
            seen.add(key)
            safe_name = html.escape(name)
            safe_url = html.escape(url, quote=True)
            as_of = html.escape(str(entry.get("as_of") or ""))
            if url:
                text = f'<a href="{safe_url}">{safe_name}</a>'
            else:
                text = safe_name
            if as_of:
                text += f" — fetched {as_of}"
            rows.append(text)

        if not rows:
            self.source_label.setText("No external sabermetric source returned data for this player.")
        else:
            self.source_label.setText("<br>".join(rows))

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
