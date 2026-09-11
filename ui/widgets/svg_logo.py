from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QLabel


class SvgLogoLabel(QLabel):
    def __init__(self, size: int = 34) -> None:
        super().__init__()
        self.logo_size = size
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_logo(self, path: str | Path | None) -> None:
        if not path:
            self.clear()
            return
        file_path = Path(path)
        if not file_path.exists():
            self.clear()
            return
        data = file_path.read_bytes()
        renderer = QSvgRenderer(QByteArray(data))
        if not renderer.isValid():
            self.clear()
            return
        pixmap = QPixmap(self.logo_size, self.logo_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        self.setPixmap(pixmap)
