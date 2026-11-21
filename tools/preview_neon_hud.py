"""Render the stage-one real Qt components with isolated, fictional example data."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    with tempfile.TemporaryDirectory(prefix='dugout-neon-preview-') as temporary:
        os.environ['LOCALAPPDATA'] = temporary
        from PyQt6.QtCore import QSettings
        from PyQt6.QtGui import QColor, QFontDatabase, QImage, QPainter
        from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget
        from config import preferences
        preferences.store = lambda: QSettings(str(Path(temporary) / 'settings.ini'), QSettings.Format.IniFormat)
        preferences.save_preferences({'data_root': str(Path(temporary) / 'runtime'), 'language': 'ko'})
        from config.i18n import set_language
        set_language('ko')
        from config.settings import THEME_QSS_PATH
        from ui.components import HudPanel, StatCard
        from ui.theme_manager import ThemeManager
        from charts import ModernSplineChart
        app = QApplication([])
        # Offscreen Qt may not discover Windows fonts in the isolated profile.
        for filename in ('segoeui.ttf', 'segoeuib.ttf', 'malgun.ttf', 'malgunbd.ttf'):
            font = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / filename
            if font.is_file():
                QFontDatabase.addApplicationFont(str(font))
        manager = ThemeManager(app, THEME_QSS_PATH.read_text(encoding='utf-8'))
        window = QWidget()
        root = QVBoxLayout(window)
        root.setContentsMargins(28, 22, 28, 22)
        title = QLabel()
        title.setObjectName('title')
        root.addWidget(title)
        root.addWidget(QLabel('1단계 · 실제 Qt 컴포넌트 미리보기 / 예시 데이터 · 새 선수 화면 배치가 아닙니다'))
        row = QHBoxLayout()
        for name, value, unit, detail in (
            ('OPS', '.892', '', '예시 · 정규시즌'),
            ('fWAR', '5.4', '', '예시 · FanGraphs'),
            ('Exit Velocity', '92.1', 'mph', '예시 · 평균 타구 속도'),
            ('Hard Hit %', '48.2', '%', '예시 · 강한 타구 비율'),
        ):
            row.addWidget(StatCard(name, value, unit, detail), 1)
        root.addLayout(row)
        panel = HudPanel()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(22, 22, 22, 22)
        panel_layout.addWidget(QLabel('공통 HUD 패널 / 선수 추이 차트 · 예시'))
        chart = ModernSplineChart()
        panel_layout.addWidget(chart)
        root.addWidget(panel, 1)
        window.resize(1360, 690)
        window.show()
        captures = []
        for accent, theme in [('blue', 'dark'), ('neon', 'dark'), ('neon', 'light')]:
            manager.set_accent(accent)
            manager.apply(theme, animate=False)
            title.setText(f'DUGOUT ATLAS / {accent.upper()} · {theme.upper()}')
            chart.plot_trend([0, 1, 2, 3, 4, 5], [1.2, 1.9, 2.4, 2.1, 3.6, 5.4], label='fWAR')
            chart.ax.set_xticks(range(6), ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep'])
            chart.ax.set_ylabel('fWAR')
            from config.theme_tokens import chart_colors
            chart.ax.yaxis.label.set_color(chart_colors()['text'])
            chart.draw()
            for _ in range(5):
                app.processEvents()
            capture = window.grab()
            capture.save(str(args.output / f'{accent}-{theme}.png'))
            captures.append(capture)
        sheet = QImage(captures[0].width(), sum(p.height() for p in captures), QImage.Format.Format_RGB32)
        sheet.fill(QColor('#050D16'))
        painter = QPainter(sheet)
        y = 0
        for capture in captures:
            painter.drawPixmap(0, y, capture)
            y += capture.height()
        painter.end()
        sheet.save(str(args.output / 'comparison.png'))
        window.close()


if __name__ == '__main__':
    main()
