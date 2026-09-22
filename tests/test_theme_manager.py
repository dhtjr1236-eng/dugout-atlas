from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QPushButton

from ui.theme_manager import (
    DARK_TOKENS,
    LIGHT_TOKENS,
    THEME_STORAGE_KEY,
    ThemeManager,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_theme_tokens_have_required_roles() -> None:
    required = {
        "--color-bg",
        "--color-surface",
        "--color-surface-muted",
        "--color-surface-selected",
        "--color-text",
        "--color-text-muted",
        "--color-text-subtle",
        "--color-border",
        "--color-border-strong",
        "--color-primary",
        "--color-primary-hover",
        "--color-primary-soft",
        "--color-success",
        "--color-warning",
        "--color-danger",
        "--shadow-card",
    }
    assert required <= set(DARK_TOKENS)
    assert required <= set(LIGHT_TOKENS)


def test_invalid_saved_theme_is_removed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    app = _app()
    settings = QSettings("Dugout Atlas", "Dugout Atlas")
    settings.setValue(THEME_STORAGE_KEY, "banana")
    settings.sync()

    manager = ThemeManager(app, "QWidget { color: {{--color-text}}; }")

    assert manager._stored_theme() is None
    assert settings.value(THEME_STORAGE_KEY, None) is None


def test_toggle_persists_and_updates_accessibility(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    app = _app()
    manager = ThemeManager(app, "QWidget { color: {{--color-text}}; }")
    manager.apply("dark", animate=False)

    button = QPushButton()
    manager.attach_button(button)
    manager.toggle()

    assert manager.current_theme == "light"
    assert str(manager.settings.value(THEME_STORAGE_KEY)) == "light"
    assert button.text() == "Dark"
    assert "Dark Theme" in button.accessibleName()
