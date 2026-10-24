from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPaintEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout
from config.theme_tokens import active_theme, tokens_for

class StatCard(QFrame):
    """영상 Frame 5 스타일의 세이버메트릭스 KPI 카드"""
    def __init__(self, title: str, main_val: str, unit: str, subtext: str,
                 indicator_color: str | None = None, watermark_text: str = "", parent=None):
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

        # 메인 지표 행 (예: 0.708 OPS)
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

        # 하단 보조 텍스트 (예: Actual Over: 3.33)
        self.subtext_label = QLabel(subtext)
        self.subtext_label.setObjectName("statCardSubtext")
        layout.addWidget(self.subtext_label)

    def set_values(self, title: str, main_val: str, unit: str = "", subtext: str = "") -> None:
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

        # 1. 배경 워터마크 (구단 로고 약어 또는 텍스트)
        if self.watermark_text:
            tokens = tokens_for(active_theme())
            watermark_color = QColor(tokens["--color-text"])
            watermark_color.setAlpha(16)
            painter.setFont(QFont("Arial", 46, QFont.Weight.Bold))
            painter.setPen(watermark_color)
            painter.drawText(self.rect().adjusted(0, 0, -15, -10),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             self.watermark_text)

        # 2. 좌측 또는 하단 컬러 액센트 인디케이터 바
        painter.setPen(Qt.PenStyle.NoPen)
        indicator = self.indicator_color or QColor(tokens_for(active_theme())["--color-primary"])
        painter.setBrush(indicator)
        painter.drawRoundedRect(14, self.height() - 4, 38, 3, 1.5, 1.5)
