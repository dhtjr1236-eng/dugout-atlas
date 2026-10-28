from __future__ import annotations

from datetime import UTC, datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QSizePolicy, QVBoxLayout

from config.i18n import tr
from services.home_service import SeasonRecap


def format_saved_time(value: str) -> str:
    try:
        stamp = datetime.fromisoformat(value)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=UTC)
        return stamp.astimezone(UTC).strftime('%Y-%m-%d %H:%M')
    except (TypeError, ValueError):
        return '—'


def format_recap_value(name: str, value: float | None, *, signed: bool = False) -> str:
    if value is None:
        return '—'
    precision = {'OPS': 3, 'HR': 0, 'ERA': 2, 'K%': 1, 'fWAR': 1}[name]
    # Avoid a negative zero after rounding; deltas are arithmetic, not rankings.
    if round(value, precision) == 0:
        value = 0.0
    result = format(value, f'{"+" if signed else ""}.{precision}f')
    return result + (' pp' if signed and name == 'K%' else '%' if name == 'K%' else '')


class SeasonRecapCard(QFrame):
    requested = pyqtSignal(int, int)

    def __init__(self, recap: SeasonRecap, season: int, parent=None, *, open_button=None):
        super().__init__(parent)
        self.setObjectName('panel')
        self.setProperty('seasonRecap', True)
        layout = QVBoxLayout(self)

        def label(text: str) -> QLabel:
            widget = QLabel(text)
            widget.setTextFormat(Qt.TextFormat.PlainText)
            widget.setWordWrap(True)
            widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            layout.addWidget(widget)
            return widget

        role = tr('Pitching') if recap.role == 'pitcher' else tr('Batting')
        label(f'{recap.name} · {role}').setObjectName('homeSection')
        label(f'{season} / {season - 1} · {tr("Regular season · saved FanGraphs statistics")}')
        self.metric_labels = []
        for metric in recap.metrics:
            current = format_recap_value(metric.name, metric.current)
            previous = format_recap_value(metric.name, metric.previous)
            delta = format_recap_value(metric.name, metric.delta, signed=True)
            self.metric_labels.append(label(
                f'{metric.name}: {season} {current} · {season - 1} {previous} · Δ {delta}'
            ))
        label(f'{tr("Saved at (UTC)")}: {season} {format_saved_time(recap.current_updated_at)}\n'
              f'{season - 1} {format_saved_time(recap.previous_updated_at)}')
        if any(metric.current is None or metric.previous is None for metric in recap.metrics):
            label(tr('Missing records: open player analysis for each season, then refresh this overview.'))
        self.open_button = open_button if open_button is not None else QPushButton(self)
        self.open_button.setText(tr('Open player analysis'))
        self.open_button.setAccessibleName(f'{recap.name} · {season} · {tr("Open player analysis")}')
        self.open_button.clicked.connect(lambda: self.requested.emit(recap.player_id, season))
        layout.addWidget(self.open_button)
