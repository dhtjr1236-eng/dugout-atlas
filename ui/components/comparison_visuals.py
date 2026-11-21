"""Presentation only: exact numbers remain in the comparison tables."""
import math
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QStyledItemDelegate
from config.i18n import tr
from config.theme_tokens import active_theme, tokens_for
from .hud_panel import HudPanel

VALUE_ROLE = int(Qt.ItemDataRole.UserRole)
RANGE_ROLE = VALUE_ROLE + 1
COLOR_ROLE = VALUE_ROLE + 2


def finite_number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(str(value).rstrip('%'))
        return result if math.isfinite(result) else None
    except (ValueError, TypeError, OverflowError):
        return None


def series_colors():
    tokens = tokens_for(active_theme())
    return [tokens['--color-primary'], tokens['--color-warning'],
            tokens['--color-success'], tokens['--color-danger']]


class ComparisonBarDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        value = index.data(VALUE_ROLE)
        bounds = index.data(RANGE_ROLE)
        if value is None or bounds is None:
            return
        low, high = bounds
        if high <= low:
            return
        painter.save()
        painter.setClipRect(option.rect)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(option.rect.adjusted(10, option.rect.height() - 9, -10, -3))
        tokens = tokens_for(active_theme())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tokens['--color-border']))
        painter.drawRoundedRect(track, 2, 2)
        zero = (max(low, min(0., high)) - low) / (high - low)
        end = (value - low) / (high - low)
        color = QColor(series_colors()[int(index.data(COLOR_ROLE) or 0) % 4])
        painter.setBrush(color)
        painter.drawRoundedRect(QRectF(track.left() + min(zero, end) * track.width(),
                                      track.top(), abs(end - zero) * track.width(), track.height()), 2, 2)
        painter.restore()


class PercentileRadar(HudPanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.names, self.series, self.metrics = [], [], []
        self.setMinimumHeight(320)
        self.setAccessibleName(tr('Season-specific percentile radar'))

    def set_data(self, names, series):
        self.names, self.series = list(names), list(series)
        self.metrics = [key for key in (series[0] if series else {}) if all(
            finite_number(s.get(key)) is not None and 0 <= finite_number(s.get(key)) <= 100 for s in series)]
        self.setMinimumHeight(320 + max(0, len(series) - 2) * 32)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        tokens = tokens_for(active_theme())
        painter.setPen(QColor(tokens['--color-text']))
        if len(self.metrics) < 3:
            painter.drawText(self.rect().adjusted(24, 24, -24, -24),
                             Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                             tr('Radar requires at least three shared percentiles. Missing values are not estimated.'))
            return
        legend_height = 20 * len(self.series) + 16
        center = QPointF(self.width() / 2, (self.height() + legend_height) / 2)
        radius = max(20, min(self.width() / 2 - 108, (self.height() - legend_height) / 2 - 38))
        def point(i, fraction):
            angle = -math.pi / 2 + 2 * math.pi * i / len(self.metrics)
            return center + QPointF(math.cos(angle), math.sin(angle)) * (radius * fraction)
        for fraction in (.25, .5, .75, 1.):
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(tokens['--color-border-strong']), 1))
            painter.drawPolygon(QPolygonF([point(i, fraction) for i in range(len(self.metrics))]))
        for i, metric in enumerate(self.metrics):
            painter.drawLine(center, point(i, 1))
            painter.setPen(QColor(tokens['--color-text-muted']))
            tip = point(i, 1.25)
            painter.drawText(QRectF(tip.x()-65, tip.y()-12, 130, 24), Qt.AlignmentFlag.AlignCenter, metric)
        for n, series in enumerate(self.series):
            color = QColor(series_colors()[n % 4])
            fill = QColor(color)
            fill.setAlpha(28)
            painter.setBrush(fill)
            painter.setPen(QPen(color, 2))
            polygon = QPolygonF([point(i, float(series[metric]) / 100) for i, metric in enumerate(self.metrics)])
            painter.drawPolygon(polygon)
            painter.setBrush(color)
            for p in polygon:
                painter.drawEllipse(p, 3, 3)
            painter.drawText(QRectF(24, 14+n*20, self.width()-48, 20),
                             Qt.AlignmentFlag.AlignLeft,
                             painter.fontMetrics().elidedText(self.names[n], Qt.TextElideMode.ElideRight, self.width()-48))
