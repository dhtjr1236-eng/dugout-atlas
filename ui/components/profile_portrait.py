"""A neutral profile placeholder, never presented as a real player photograph."""
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QWidget
from config.i18n import tr
from config.theme_tokens import active_theme, tokens_for


class ProfilePortrait(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(144, 176)
        self.number = '—'
        self.player_id = None
        self.photo = QPixmap()
        self.setAccessibleName(tr('Player profile placeholder'))

    def set_profile(self, profile):
        if self.player_id != profile.id:
            self.photo = QPixmap()
        self.player_id = profile.id
        self.number = str(profile.primary_number or '—')
        self.update()

    def clear_photo(self):
        self.photo = QPixmap()
        self.setAccessibleName(tr('Player profile placeholder'))
        self.setToolTip('')
        self.update()

    def set_photo(self, player_id, data):
        if self.player_id != player_id or not data:
            return
        photo = QPixmap()
        if photo.loadFromData(data):
            self.photo = photo
            self.setAccessibleName(tr('MLB player portrait'))
            self.setToolTip(tr('MLB official portrait · current image, not season-specific'))
            self.update()

    def refresh_theme_style(self):
        self.update()

    def paintEvent(self, event):
        colors = tokens_for(active_theme())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(colors['--color-border-strong']), 1))
        painter.setBrush(QColor(colors['--color-surface-muted']))
        painter.drawRoundedRect(QRectF(2, 2, 140, 172), 8, 8)
        if not self.photo.isNull():
            photo = self.photo.scaled(136, 168, Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap((self.width()-photo.width())//2, (self.height()-photo.height())//2, photo)
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colors['--color-surface-selected']))
        painter.drawEllipse(QRectF(48, 28, 48, 48))
        body = QPainterPath()
        body.moveTo(20, 145)
        body.cubicTo(20, 62, 124, 62, 124, 145)
        body.closeSubpath()
        painter.drawPath(body)
        painter.setPen(QColor(colors['--color-primary']))
        painter.setFont(QFont('Segoe UI', 25, QFont.Weight.Bold))
        painter.drawText(QRectF(20, 90, 104, 50), Qt.AlignmentFlag.AlignCenter, self.number)
