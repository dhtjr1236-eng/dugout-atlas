from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from config.logging_config import configure_logging
from config.settings import QSS_PATH, SETTINGS, ensure_runtime_dirs
from controllers.app_controller import AppController
from database.sqlite_manager import SQLiteManager
from services.convenience_features import install_convenience_features
from services.live_scoring import install_live_scoring_support
from services.player_enhancements import install_player_enhancements
from services.running_metrics import install_running_support
from ui.main_window import MainWindow


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
    if QSS_PATH.exists():
        app.setStyleSheet(QSS_PATH.read_text(encoding="utf-8"))

    db = SQLiteManager()
    window = MainWindow()
    controller = AppController(window, db)
    # Keep a strong reference for the lifetime of the window.
    window.controller = controller  # type: ignore[attr-defined]
    window.show()
    controller.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
