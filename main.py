from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from config.logging_config import configure_logging
from config.settings import SETTINGS, THEME_QSS_PATH, ensure_runtime_dirs
from controllers.app_controller import AppController
from database.sqlite_manager import SQLiteManager
from services.convenience_features import install_convenience_features
from services.live_scoring import install_live_scoring_support
from services.player_enhancements import install_player_enhancements
from services.running_metrics import install_running_support
from ui.main_window import MainWindow
from ui.theme_manager import ThemeManager


def main() -> int:
    ensure_runtime_dirs()
    configure_logging()
    install_running_support()
    install_player_enhancements()
    install_live_scoring_support()
    install_convenience_features()
    app = QApplication(sys.argv)
    app.setApplicationName(SETTINGS.app_name)
    app.setApplicationVersion(SETTINGS.app_version)
    theme_template = (
        THEME_QSS_PATH.read_text(encoding="utf-8")
        if THEME_QSS_PATH.exists()
        else ""
    )
    theme_manager = ThemeManager(app, theme_template)

    db = SQLiteManager()
    window = MainWindow()
    theme_manager.attach_button(window.theme_button)

    def refresh_theme_dependent_content() -> None:
        player_view = window.player_view
        bundle = player_view.current_bundle
        if bundle is None:
            return
        if bundle.profile.is_pitcher:
            payload = getattr(player_view, "_pitcher_period_payload", {}) or None
            player_view._show_pitcher(bundle, payload)
        else:
            player_view._show_batter(bundle)

    theme_manager.add_listener(refresh_theme_dependent_content)
    window.theme_manager = theme_manager  # type: ignore[attr-defined]
    controller = AppController(window, db)
    # Keep a strong reference for the lifetime of the window.
    window.controller = controller  # type: ignore[attr-defined]
    window.show()
    controller.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
