from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPaintEvent, QPolygonF
from PyQt6.QtWidgets import QWidget
from config.theme_tokens import active_theme, tokens_for

class BaseballDiamondWidget(QWidget):
    """1·2·3루 주자 상황을 렌더링하는 컴팩트 다이아몬드 위젯"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(70, 70)
        self.runner_1b = False
        self.runner_2b = False
        self.runner_3b = False

    def update_runners(self, r1: bool, r2: bool, r3: bool):
        self.runner_1b = r1
        self.runner_2b = r2
        self.runner_3b = r3
        self.update()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        tokens = tokens_for(active_theme())

        cx, cy = self.width() / 2, self.height() / 2
        d = 18  # 중심에서의 베이스 거리
        base_size = 6

        bases = [
            (QPointF(cx + d, cy), self.runner_1b),      # 1루
            (QPointF(cx, cy - d), self.runner_2b),      # 2루
            (QPointF(cx - d, cy), self.runner_3b),      # 3루
            (QPointF(cx, cy + d), False)                # 홈 플레이트
        ]

        # 베이스라인 그리기
        painter.setPen(QColor(tokens["--color-border-strong"]))
        painter.drawLine(int(cx), int(cy + d), int(cx + d), int(cy))
        painter.drawLine(int(cx + d), int(cy), int(cx), int(cy - d))
        painter.drawLine(int(cx), int(cy - d), int(cx - d), int(cy))
        painter.drawLine(int(cx - d), int(cy), int(cx), int(cy + d))

        # 베이스 다이아몬드 그리기
        for pt, occupied in bases:
            poly = QPolygonF([
                QPointF(pt.x(), pt.y() - base_size),
                QPointF(pt.x() + base_size, pt.y()),
                QPointF(pt.x(), pt.y() + base_size),
                QPointF(pt.x() - base_size, pt.y())
            ])
            if occupied:
                painter.setBrush(QBrush(QColor(tokens["--color-danger"])))
                painter.setPen(Qt.PenStyle.NoPen)
            else:
                painter.setBrush(QBrush(QColor(tokens["--color-surface-muted"])))
                painter.setPen(QColor(tokens["--color-border"]))
            painter.drawPolygon(poly)
