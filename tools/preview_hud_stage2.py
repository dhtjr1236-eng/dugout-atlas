"""Render the actual player and advanced compare screens without external requests."""
import argparse
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    with tempfile.TemporaryDirectory(prefix='dugout-stage2-') as temporary:
        os.environ['LOCALAPPDATA'] = temporary
        from PyQt6.QtCore import QSettings
        from PyQt6.QtGui import QFontDatabase
        from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
        from config import preferences
        preferences.store = lambda: QSettings(str(Path(temporary) / 'settings.ini'), QSettings.Format.IniFormat)
        preferences.save_preferences({'data_root': str(Path(temporary) / 'runtime'), 'language': 'ko'})
        from config.i18n import set_language
        set_language('ko')
        app = QApplication([])
        for filename in ('segoeui.ttf', 'segoeuib.ttf', 'malgun.ttf', 'malgunbd.ttf'):
            path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / filename
            if path.is_file():
                QFontDatabase.addApplicationFont(str(path))
        from config.settings import THEME_QSS_PATH
        from ui.theme_manager import ThemeManager
        from services.player_enhancements import install_player_enhancements
        from ui.player_view import PlayerView
        from ui.advanced_compare_window import AdvancedCompareWindow
        from models.player import PlayerBundle, PlayerProfile
        install_player_enhancements()
        manager = ThemeManager(app, THEME_QSS_PATH.read_text(encoding='utf-8'))
        manager.set_accent('neon')
        manager.apply('dark', animate=False)
        a = PlayerBundle(PlayerProfile(1, 'EXAMPLE PLAYER A', 'EXAMPLE', 'CF', 26, 'R', 'R', primary_number='44'),
                         basic={'avg': .287, 'obp': .365, 'slg': .527, 'ops': .892, 'homeRuns': 28, 'rbi': 86},
                         fangraphs={'fWAR': 5.4, 'wOBA': .376, 'wRC+': 142, 'OPS': .892},
                         bref={'bWAR': 4.8},
                         statcast={'Average Exit Velocity': 92.1, 'Hard Hit %': 48.2, 'xBA': .285, 'xSLG': .52, 'xwOBA': .37},
                         history=[{'Season': year, 'WAR': war, 'wRC+': wrc} for year, war, wrc in [(2022,2.4,110),(2023,3.6,124),(2024,4.1,130),(2025,5.4,142)]])
        b = PlayerBundle(PlayerProfile(2, 'EXAMPLE PLAYER B', 'EXAMPLE', 'CF'),
                         basic={'avg': .274, 'obp': .342, 'slg': .468, 'ops': .810},
                         fangraphs={'fWAR': 3.8, 'wRC+': 121}, bref={'bWAR': 3.6},
                         statcast={'Average Exit Velocity': 89.5, 'xBA': .26, 'xSLG': .46, 'xwOBA': .33})
        player = PlayerView()
        player.set_bundle(a)
        player.set_available_seasons([2025, 2026], 2025) if hasattr(player, 'set_available_seasons') else None
        player.chart_tabs.setCurrentIndex(3)
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.addWidget(QLabel('2단계 실제 선수 화면 / 오프라인 예시 데이터 · 실제 선수 성적이 아닙니다'))
        layout.addWidget(player)
        wrapper.resize(1440, 1080)
        compare = AdvancedCompareWindow(SimpleNamespace(fangraphs=SimpleNamespace(db=SimpleNamespace())), 2026)
        compare.subtitle.setText('오프라인 예시 데이터 · 백분위도 예시 분포에서 계산한 시연값입니다')
        for slot, year, bundle in zip(compare.slots, [2025, 2026], [a, b]):
            slot.season.setValue(year)
            slot.bundle = bundle
            slot.player_id = bundle.profile.id
            slot.edit.blockSignals(True)
            slot.edit.setText(bundle.profile.full_name)
            slot.edit.blockSignals(False)
            slot.status.setText('EXAMPLE / CF')
        for year in (2025, 2026):
            compare.service._dist_cache[year] = {'xBA':[.22,.24,.26,.28,.30], 'xSLG':[.32,.38,.44,.50,.56],
                                                'xwOBA':[.27,.30,.33,.36,.39], 'Avg EV':[85,87,89,91,93]}
        compare._render()
        compare._sync_race()
        compare.resize(1440, 1120)
        for theme in ('dark', 'light'):
            manager.apply(theme, animate=False)
            for name, window in [('player', wrapper), ('compare', compare)]:
                window.show()
                for _ in range(8):
                    app.processEvents()
                window.grab().save(str(args.output / f'{name}-neon-{theme}.png'))
                window.hide()
        compare.close()
        wrapper.close()


if __name__ == '__main__':
    main()
