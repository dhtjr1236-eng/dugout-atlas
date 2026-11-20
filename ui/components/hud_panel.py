"""Shared HUD frame; no animation timers or data dependencies."""
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QFrame

from config.theme_tokens import active_theme, glow_enabled, hud_enabled, tokens_for


class HudPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("hudPanel", True)

    def refresh_theme_style(self):
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not hud_enabled():
            return
        tokens = tokens_for(active_theme())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        left, top, right, bottom = 5., 5., self.width() - 5., self.height() - 5.
        path = QPainterPath()
        length = min(22., self.width() / 6, self.height() / 4)
        for x, y, dx, dy in ((left, top, 1, 1), (right, top, -1, 1),
                              (left, bottom, 1, -1), (right, bottom, -1, -1)):
            path.moveTo(x, y + dy * length)
            path.lineTo(x, y + dy * 5)
            path.lineTo(x + dx * 5, y)
            path.lineTo(x + dx * length, y)
        color = QColor(tokens["--color-hud-line"])
        if glow_enabled():
            halo = QColor(color)
            halo.setAlpha(35)
            painter.setPen(QPen(halo, 5))
            painter.drawPath(path)
        painter.setPen(QPen(color, 1.25))
        painter.drawPath(path)
        # Small frame ticks, kept outside the content margins.
        color.setAlpha(110)
        painter.setPen(QPen(color, 1))
        for i in range(3):
            x = right - 30 - i * 9
            painter.drawLine(QPointF(x, bottom), QPointF(x - 5, bottom))
