from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from config.logging_config import configure_logging
from config.settings import QSS_PATH, ensure_runtime_dirs
from controllers.app_controller import AppController
from database.sqlite_manager import SQLiteManager
from ui.main_window import MainWindow


def main() -> int:
    ensure_runtime_dirs()
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("MLB Advanced Gameday")
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
