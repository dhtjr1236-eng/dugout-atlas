from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPaintEvent,
    QLinearGradient,
)
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QVBoxLayout

from config.theme_tokens import active_theme, tokens_for, glow_enabled, hud_enabled
from .hud_panel import HudPanel


class StatCard(HudPanel):
    """영상 Frame 5 스타일의 세이버메트릭스 KPI 카드"""

    def __init__(
        self,
        title: str,
        main_val: str,
        unit: str,
        subtext: str,
        indicator_color: str | None = None,
        watermark_text: str = "",
        parent=None,
    ):
        super().__init__(parent)

        self.indicator_color = QColor(indicator_color) if indicator_color else None
        self.watermark_text = watermark_text

        self.setObjectName("StatCard")
        self.setMinimumSize(220, 110)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("statCardTitle")
        layout.addWidget(self.title_label)

        val_row = QHBoxLayout()
        val_row.setSpacing(6)

        self.value_label = QLabel(main_val)
        self.value_label.setObjectName("statCardValue")

        self.unit_label = QLabel(unit)
        self.unit_label.setObjectName("statCardUnit")

        val_row.addWidget(self.value_label)
        val_row.addWidget(self.unit_label)
        val_row.addStretch()

        layout.addLayout(val_row)

        self.subtext_label = QLabel(subtext)
        self.subtext_label.setObjectName("statCardSubtext")
        layout.addWidget(self.subtext_label)
        self._value_glow = QGraphicsDropShadowEffect(self.value_label)
        self._value_glow.setOffset(0, 0)
        self._value_glow.setBlurRadius(14)
        self.value_label.setGraphicsEffect(self._value_glow)
        self.refresh_theme_style()

    def refresh_theme_style(self):
        if hasattr(self, "_value_glow"):
            color = QColor(tokens_for(active_theme())["--color-hud-line"])
            color.setAlpha(110)
            self._value_glow.setColor(color)
            self._value_glow.setEnabled(glow_enabled())
        super().refresh_theme_style()

    def set_values(
        self,
        title: str,
        main_val: str,
        unit: str = "",
        subtext: str = "",
    ) -> None:
        self.title_label.setText(title)
        self.value_label.setText(main_val)
        self.unit_label.setText(unit)
        self.unit_label.setVisible(bool(unit))
        self.subtext_label.setText(subtext)
        self.subtext_label.setVisible(bool(subtext))

    def paintEvent(self, a0: QPaintEvent):
        super().paintEvent(a0)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        tokens = tokens_for(active_theme())

        # 1. 배경 워터마크
        if self.watermark_text:
            watermark_color = QColor(tokens["--color-text"])
            watermark_color.setAlpha(16)

            painter.setFont(
                QFont(
                    "Arial",
                    46,
                    QFont.Weight.Bold,
                )
            )

            painter.setPen(watermark_color)

            painter.drawText(
                self.rect().adjusted(0, 0, -15, -10),
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignVCenter,
                self.watermark_text,
            )

        # 3. 하단 인디케이터 (그라데이션)
        indicator = (
            self.indicator_color
            or QColor(tokens["--color-primary"])
        )

        width = self.width() - 36 if hud_enabled() else 38
        grad = QLinearGradient(18, 0, 18 + width, 0)
        grad.setColorAt(0.0, indicator)
        fade = QColor(indicator)
        fade.setAlpha(15)
        grad.setColorAt(1.0, fade if hud_enabled() else indicator.lighter(160))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(grad)

        painter.drawRoundedRect(
            18 if hud_enabled() else 14,
            self.height() - 13 if hud_enabled() else self.height() - 4,
            width,
            2 if hud_enabled() else 3,
            1.5,
            1.5,
        )
