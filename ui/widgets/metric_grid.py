from __future__ import annotations

from config.i18n import tr

from typing import Any

from PyQt6.QtWidgets import QGridLayout, QLabel, QWidget


def format_value(value: Any, *, percent: bool = False) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, float):
        if percent:
            return f"{value:.1f}%"
        if abs(value) < 1:
            return f"{value:.3f}"
        return f"{value:.2f}"
    text = str(value)
    if percent and not text.endswith("%"):
        return f"{text}%"
    return text


class MetricGrid(QWidget):
    def __init__(self, columns: int = 4) -> None:
        super().__init__()
        self.columns = columns
        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

    def set_metrics(self, metrics: list[tuple[str, Any, bool]]) -> None:
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        for index, (name, value, percent) in enumerate(metrics):
            row = (index // self.columns) * 2
            col = index % self.columns
            name_label = QLabel(tr(name))
            name_label.setObjectName("subtitle")
            value_label = QLabel(tr(format_value(value, percent=percent)))
            value_label.setObjectName("metricValue")
            self.layout.addWidget(name_label, row, col)
            self.layout.addWidget(value_label, row + 1, col)
