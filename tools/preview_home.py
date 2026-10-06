"""Render the real Qt window with isolated, clearly labelled offline example data."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    with tempfile.TemporaryDirectory(prefix='dugout-home-preview-') as temporary:
        root=Path(temporary)
        os.environ['LOCALAPPDATA']=str(root/'local')
        from PyQt6.QtCore import QSettings, QDate
        from PyQt6.QtWidgets import QApplication
        from config import preferences
        preferences.store=lambda: QSettings(str(root/'settings.ini'),QSettings.Format.IniFormat)
        preferences.save_preferences({'data_root':str(root/'runtime'),'language':'ko'})
        from config.i18n import set_language
        set_language('ko')
        from services.favorites_service import FavoritesService
        favorites=FavoritesService()
        for player_id,name,team in [(660271,'오타니 쇼헤이','LAD'),(592450,'애런 저지','NYY'),(808982,'이정후','SF')]:
            favorites.toggle_player(player_id,name,team)
        from services.running_metrics import install_running_support
        from services.player_enhancements import install_player_enhancements
        from services.live_scoring import install_live_scoring_support
        from services.convenience_features import install_convenience_features
        from services.compare_league_context import install_compare_league_position
        from services.player_name_localization import install_player_name_localization
        for install in (install_running_support,install_player_enhancements,install_live_scoring_support,
                        install_convenience_features,install_compare_league_position,install_player_name_localization):
            install()
        app=QApplication([])
        from config.settings import THEME_QSS_PATH
        from ui.main_window import MainWindow
        from ui.theme_manager import ThemeManager
        from services.home_service import HomeSnapshot
        manager=ThemeManager(app,THEME_QSS_PATH.read_text(encoding='utf-8'))
        window=MainWindow();window.theme_manager=manager
        window.setWindowTitle('Dugout Atlas · 홈 화면 미리보기 · 예시 데이터')
        home=window.home_view
        home.season.setValue(2025)
        home.set_snapshot(HomeSnapshot(2025,tuple(favorites.load()['players']),3,2,6,'2025-11-03T09:00:00+00:00'))
        home.set_schedule_state('empty','2025-12-01')
        home.eyebrow.setText('예시 데이터  ·  DUGOUT ATLAS / SEASON DESK')
        window.date_edit.blockSignals(True);window.date_edit.setDate(QDate(2025,12,1));window.date_edit.blockSignals(False)
        window.statusBar().showMessage('예시 데이터로 렌더링한 실제 UI · 네트워크 요청 없음')
        window.resize(1440,1100)
        window.show()
        for theme in ('dark','light'):
            manager.apply(theme,animate=False)
            for _ in range(8):app.processEvents()
            window.grab().save(str(args.output/f'Dugout_Atlas_Home_{theme}.png'))
        # A narrow viewport checks that home cards reflow and scrolling stays usable.
        from ui.home_view import HomeView
        narrow=HomeView();narrow.resize(500,820);narrow.show()
        narrow.eyebrow.setText('예시 데이터 · 좁은 화면 확인')
        for _ in range(8):app.processEvents()
        assert narrow._columns==1
        narrow.grab().save(str(args.output/'Dugout_Atlas_Home_narrow.png'))
        narrow.close();window.close();app.processEvents()

if __name__=='__main__':
    main()
