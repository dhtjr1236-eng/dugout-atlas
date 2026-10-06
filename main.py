from __future__ import annotations

import sys
from PyQt6.QtWidgets import QApplication


def main() -> int:
    from config.logging_config import configure_logging
    from config.settings import SETTINGS, THEME_QSS_PATH, ensure_runtime_dirs
    from controllers.app_controller import AppController
    from database.sqlite_manager import SQLiteManager
    from services.compare_league_context import install_compare_league_position
    from services.convenience_features import install_convenience_features
    from services.live_scoring import install_live_scoring_support
    from services.player_enhancements import install_player_enhancements
    from services.player_name_localization import install_player_name_localization
    from services.running_metrics import install_running_support
    from ui.main_window import MainWindow
    from ui.theme_manager import ThemeManager

    from config.preferences import read_preferences
    from config.i18n import set_language
    set_language(read_preferences()["language"])
    configure_logging()
    ensure_runtime_dirs()
    install_running_support()
    install_player_enhancements()
    install_live_scoring_support()
    install_convenience_features()
    install_compare_league_position()
    install_player_name_localization()
    app = QApplication(sys.argv)
    app.setApplicationName(SETTINGS.app_name)
    app.setApplicationVersion(SETTINGS.app_version)
    theme_template = THEME_QSS_PATH.read_text(encoding="utf-8") if THEME_QSS_PATH.exists() else ""
    theme_manager = ThemeManager(app, theme_template)
    db = SQLiteManager()
    window = MainWindow()
    def refresh_theme_dependent_content() -> None:
        player_view = window.player_view
        bundle = player_view.current_bundle
        if bundle is None: return
        if bundle.profile.is_pitcher: player_view._show_pitcher(bundle, getattr(player_view, "_pitcher_period_payload", {}) or None)
        else: player_view._show_batter(bundle)
    theme_manager.add_listener(refresh_theme_dependent_content)
    window.theme_manager = theme_manager
    controller = AppController(window, db)
    window.controller = controller
    window.show()
    controller.start()
    return app.exec()

if __name__ == "__main__":
    import logging
    import sqlite3
    try:
        raise SystemExit(main())
    except (OSError, sqlite3.Error):
        logging.getLogger(__name__).error("Application data could not be opened; check permissions and disk space")
        from PyQt6.QtWidgets import QMessageBox
        error_app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, "Dugout Atlas", "사용자 데이터에 접근할 수 없습니다. 폴더 권한과 디스크 공간을 확인해 주세요.")
        raise SystemExit(1)
