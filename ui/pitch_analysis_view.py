"""Beginner-facing presentation of existing pitcher analysis summaries."""
from __future__ import annotations

from typing import Any
from config.i18n import tr
from config.theme_tokens import chart_colors
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties, fontManager
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QTabWidget, QComboBox,
    QTableWidget, QTableWidgetItem, QGroupBox, QSizePolicy,
)


class PitchAnalysisView(QWidget):
    requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.payload: dict[str, Any] = {}
        self._state = 'idle'
        root = QVBoxLayout(self)
        self.load = QPushButton(tr('Load pitcher analysis'))
        self.load.clicked.connect(self.requested.emit)
        root.addWidget(self.load)
        self.status = self.label(root)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)
        profile = QWidget()
        layout = QVBoxLayout(profile)
        self.metric = QComboBox()
        self.metric.addItem(tr('Velocity distribution (mph)'), 'release_speed')
        self.metric.addItem(tr('Spin distribution (rpm)'), 'release_spin_rate')
        layout.addWidget(self.metric)
        self.profile_help = self.label(layout)
        self.figure = Figure(figsize=(7, 3.8))
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(300)
        layout.addWidget(self.canvas)
        self.profile_pitch = QComboBox()
        layout.addWidget(self.profile_pitch)
        self.profile_summary = self.label(layout)
        self.profile_sample = self.label(layout)
        self.details_toggle = QPushButton(tr('Show details'))
        self.details_toggle.setCheckable(True)
        layout.addWidget(self.details_toggle)
        self.details = QGroupBox(tr('Distribution details'))
        details_layout = QVBoxLayout(self.details)
        self.profile = QTableWidget()
        self.profile.setMaximumHeight(210)
        details_layout.addWidget(self.profile)
        self.detail_help = self.label(details_layout)
        layout.addWidget(self.details)
        self.details.hide()
        self.details_toggle.toggled.connect(self.details.setVisible)
        self.tabs.addTab(profile, tr('Pitch Profile'))
        matchup = QWidget()
        layout = QVBoxLayout(matchup)
        self.mode = QComboBox()
        self.mode.addItem(tr('Batter handedness'), 'hand')
        self.mode.addItem(tr('Balls-strikes'), 'count')
        layout.addWidget(self.mode)
        self.match_status = self.label(layout)
        self.match_choice = QComboBox()
        layout.addWidget(self.match_choice)
        self.match_summary = self.label(layout)
        self.match_sample = self.label(layout)
        self.match_figure = Figure(figsize=(7, 2.4))
        self.match_canvas = FigureCanvasQTAgg(self.match_figure)
        self.match_canvas.setMinimumHeight(160)
        layout.addWidget(self.match_canvas)
        self.matchup = QTableWidget()
        self.matchup.setMaximumHeight(270)
        layout.addWidget(self.matchup)
        self.match_help = self.label(layout)
        self.tabs.addTab(matchup, tr('Matchup'))
        from ui.pitch_change_view import PitchChangeView
        self.change = PitchChangeView()
        self.tabs.addTab(self.change, tr('Change'))
        self.metric.currentIndexChanged.connect(self.render)
        self.mode.currentIndexChanged.connect(self.render)
        self.profile_pitch.currentIndexChanged.connect(self.render)
        self.match_choice.currentIndexChanged.connect(self.render)
        for combo in (self.metric, self.mode, self.profile_pitch, self.match_choice):
            combo.setMinimumHeight(32)
        self.render()

    @staticmethod
    def label(layout: QVBoxLayout) -> QLabel:
        label = QLabel()
        label.setWordWrap(True)
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout.addWidget(label)
        return label

    @staticmethod
    def number(value: Any) -> str:
        return '—' if value is None else f'{value:.2f}' if isinstance(value, float) else str(value)

    @staticmethod
    def choices(combo: QComboBox, choices: list[tuple[str, str]]) -> None:
        old = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for text, key in choices:
            combo.addItem(text, key)
        combo.setCurrentIndex(max(0, combo.findData(old)))
        combo.blockSignals(False)

    def reset(self) -> None:
        self.change.reset()
        self.payload = {}
        self._state = 'idle'
        self.load.setEnabled(True)
        self.render()

    def loading(self) -> None:
        self.load.setEnabled(False)
        self._state = 'loading'
        self.refresh_status()

    def failed(self) -> None:
        self.load.setEnabled(True)
        self._state = 'failed'
        self.refresh_status()

    def set_result(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.load.setEnabled(True)
        self._state = 'result'
        self.render()

    def refresh_status(self) -> None:
        messages = {'idle': 'Not loaded', 'loading': 'Loading pitcher analysis…',
                    'failed': 'Analysis failed; existing player data remains available.'}
        if self._state in messages:
            self.status.setText(tr(messages[self._state]))
            return
        labels = {'ready': 'Ready', 'partial': 'Partial success / interpret with caution',
                  'empty': 'No data', 'unverified': 'Unverified'}
        self.status.setText(tr(labels.get(self.payload.get('status'), 'Unverified'))
                            + f" · {self.payload.get('season')} · N={self.payload.get('total', 0)} · "
                            + tr('Regular-season pitches only')
                            + f" · {tr('Unclassified')}={self.payload.get('unknown_pitch', 0)}")

    @staticmethod
    def fill(table: QTableWidget, headings: list[str], rows: list[list[Any]], help_text: dict[str, str]) -> None:
        table.setColumnCount(len(headings))
        table.setHorizontalHeaderLabels([tr(h) for h in headings])
        table.setRowCount(len(rows))
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for j, heading in enumerate(headings):
            table.horizontalHeaderItem(j).setToolTip(tr(help_text.get(heading, '')))
        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                item = QTableWidgetItem(tr(PitchAnalysisView.number(value)))
                item.setToolTip(tr(help_text.get(headings[j], '')))
                table.setItem(i, j, item)
        table.resizeColumnsToContents()

    @staticmethod
    def axes(figure: Figure):
        figure.clear()
        colors = chart_colors()
        figure.patch.set_facecolor(colors['figure'])
        ax = figure.add_subplot(111)
        ax.set_facecolor(colors['axes'])
        ax.tick_params(colors=colors['text'])
        for spine in ax.spines.values():
            spine.set_color(colors['border'])
        return ax, colors

    def refresh_presentation(self) -> None:
        """Called after the app translates existing widgets; calculations stay untouched."""
        self.render()

    def render(self, *_args) -> None:
        self.refresh_status()
        unit = 'mph' if self.metric.currentData() == 'release_speed' else 'rpm'
        rows = [r for r in self.payload.get('profile', []) if r['field'] == self.metric.currentData()]
        self.choices(self.profile_pitch, [(r['pitch'], r['pitch']) for r in rows])
        self.profile_help.setText(tr('Center line (Md): median. Box: central 50% (Q1–Q3). Width of that interval: IQR.'))
        details_help = {
            'Median': 'Median: the middle value when valid pitches are ordered.',
            'IQR': 'IQR: Q3 minus Q1; the width of the central 50%.',
            'SD': 'SD: spread around the mean; unavailable with fewer than two valid pitches.',
            'P10': 'P10: the 10th percentile of valid observations.',
            'P90': 'P90: the 90th percentile of valid observations.',
            'Valid N': 'Valid N: pitches with a usable value for this metric.',
            'Missing': 'Missing: excluded or unusable values; never filled with zero.',
        }
        self.fill(self.profile, ['Pitch', 'Valid N', 'Total N', 'Missing', 'Median', 'IQR', 'SD', 'P10', 'P90'],
                  [[r['pitch'], r['n'], r['total'], r['missing'], r.get('median'), r.get('iqr'), r.get('sd'), r.get('p10'), r.get('p90')] for r in rows], details_help)
        self.detail_help.setText(tr('Whiskers show P10–P90, not minima and maxima. SD describes spread, not quality.'))
        self.metric.setToolTip(tr('Velocity: release speed in mph.' if unit == 'mph' else 'Spin: rotations per minute (rpm).'))
        ax, colors = self.axes(self.figure)
        valid = [r for r in rows if r['n']]
        # Existing stored quartiles and percentiles are used directly, without recomputation.
        self.canvas.setMinimumHeight(max(300, 60 * len(valid)))
        stats = [dict(label=f"{r['pitch']}  N={r['n']}", med=r['median'], q1=r['q1'], q3=r['q3'],
                      whislo=r['p10'], whishi=r['p90'], fliers=[]) for r in valid]
        if stats:
            ax.bxp(stats, vert=False, showfliers=False,
                   boxprops={'color': colors['text']}, whiskerprops={'color': colors['muted']},
                   capprops={'color': colors['muted']}, medianprops={'color': colors['primary']})
            for i, row in enumerate(valid, 1):
                # Numeric chart annotations are language-independent; Qt explains their names.
                text = f"Md {row['median']:.2f} {unit}\n50% [{row['q1']:.2f}, {row['q3']:.2f}] {unit}"
                ax.text(1.02, i, text, transform=ax.get_yaxis_transform(), va='center', fontsize=9, color=colors['text'])
        else:
            ax.text(.5, .5, '—', transform=ax.transAxes, ha='center', color=colors['text'])
        ax.set_xlabel(unit, color=colors['text'])
        self.figure.subplots_adjust(left=.17, right=.66, bottom=.17, top=.95)
        self.canvas.draw_idle()
        selected = next((r for r in rows if r['pitch'] == self.profile_pitch.currentData()), None)
        if selected and selected['n']:
            r = selected
            self.profile_summary.setText(f"{r['pitch']} · "+tr('Median')+f" {self.number(r['median'])} {unit} · "+tr('Central 50%')+f" {self.number(r['q1'])}–{self.number(r['q3'])} {unit}")
            self.profile_sample.setText(tr('Valid N')+f" {r['n']}/{r['total']} · "+tr('Missing')+f" {r['missing']} · "+tr('Interpret with caution' if r['small'] else 'Observed sample'))
        else:
            self.profile_summary.setText(tr('Unverified / no valid distribution'))
            self.profile_sample.setText(tr('Valid N')+' 0')
        split = self.payload.get('matchup', {}).get(self.mode.currentData(), {'status': 'unverified', 'rows': []})
        match_rows = split['rows']
        self.choices(self.match_choice, [(f"{r['condition']} / {r['pitch']}", f"{r['condition']}:{r['pitch']}") for r in match_rows])
        self.match_status.setText(tr('Unverified') if split['status'] == 'unverified' else tr('Valid context')+f" {split.get('valid', 0)}/{split.get('total', 0)}")
        self.match_help.setText(tr('Usage: share of classified pitches in this context. Whiff: misses divided by swings. L/R means left/right batter; balls-strikes shows the recorded count.'))
        table_rows = []
        for r in match_rows:
            fraction = '—' if r['whiffs'] is None or r['swings'] is None else f"{r['whiffs']}/{r['swings']}"
            whiff = self.number(r['whiff'])+'%' if r['whiff'] is not None else '—'
            table_rows.append([r['condition'], r['pitch'], r['pitches'], f"{r['pitches']}/{r['denominator']}", r['usage'],
                               fraction+' · '+whiff, r['outcome_n'], 'Interpret with caution' if r['small'] else 'Observed sample'])
        self.fill(self.matchup, ['Context', 'Pitch', 'Pitches', 'Usage numerator/denominator', 'Usage %', 'Whiffs / swings · Whiff %', 'Outcome N', 'Sample'], table_rows,
                  {'Usage %': 'Usage denominator: classified pitches in this context.', 'Whiffs / swings · Whiff %': 'Whiff denominator: swings, not all pitches.'})
        r = next((r for r in match_rows if f"{r['condition']}:{r['pitch']}" == self.match_choice.currentData()), None)
        ax, colors = self.axes(self.match_figure)
        if r:
            whiff = self.number(r['whiff'])+'%' if r['whiff'] is not None else tr('Not calculated')
            fraction = '—' if r['swings'] is None else f"{r['whiffs']}/{r['swings']}"
            self.match_summary.setText(f"{r['condition']} / {r['pitch']} · "+tr('Usage %')+f" {r['usage']:.2f}% ({r['pitches']}/{r['denominator']}) · Whiff {whiff} ({fraction})")
            self.match_sample.setText(tr('Pitches')+f" {r['pitches']} · "+tr('Swings')+f" {self.number(r['swings'])} · "+tr('Outcome N')+f" {r['outcome_n']}/{r['pitches']} · "+tr('Interpret with caution' if r['small'] else 'Observed sample'))
            values = [r['usage'], r['whiff']]
            for i, value in enumerate(values):
                if value is not None:
                    ax.barh(i, value, color=colors['primary'])
                    ax.text(min(value+1, 98), i, f'{value:.2f}%', va='center', color=colors['text'])
            ax.set_yticks([0, 1], [tr('Usage %'), 'Whiff %'])
            families = {f.name for f in fontManager.ttflist}
            font = FontProperties(family=[name for name in ['Malgun Gothic', 'Yu Gothic', 'Noto Sans CJK KR', 'DejaVu Sans'] if name in families])
            for label in ax.get_yticklabels():
                label.set_fontproperties(font)
            ax.set_xlim(0, 110)
        else:
            self.match_summary.setText(tr('No data'))
            self.match_sample.setText(tr('Unverified'))
        ax.set_xlabel('%', color=colors['text'])
        self.match_figure.subplots_adjust(left=.15, right=.97, bottom=.25, top=.93)
        self.match_canvas.draw_idle()

# Dugout Atlas
# Copyright (c) 2026 dhtjr1236-eng
# Unauthorized redistribution or rebranding is prohibited.
