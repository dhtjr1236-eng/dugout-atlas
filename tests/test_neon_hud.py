import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

from config import preferences
from config.settings import THEME_QSS_PATH
from config.theme_tokens import active_accent, active_theme, set_active_accent, set_active_theme
from ui.components import HudPanel, StatCard
from ui.theme_manager import ACCENT_STORAGE_KEY, ThemeManager


@pytest.fixture
def context(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / 'settings.ini'), QSettings.Format.IniFormat)
    monkeypatch.setattr(preferences, 'store', lambda: settings)
    previous = app.styleSheet(), active_theme(), active_accent()
    manager = ThemeManager(app, THEME_QSS_PATH.read_text(encoding='utf-8'))
    yield app, manager
    app.setStyleSheet(previous[0])
    set_active_theme(previous[1])
    set_active_accent(previous[2])


def test_neon_selection_persistence_and_live_existing_card(context):
    app, manager = context
    manager.set_accent('blue')
    manager.apply('dark', animate=False)
    card = StatCard('OPS', '.900', '', 'Example')
    card.show()
    try:
        manager.set_accent('neon')
        app.processEvents()
        assert manager.settings.value(ACCENT_STORAGE_KEY) == 'neon'
        assert card._value_glow.isEnabled()
        assert card.value_label.palette().color(QPalette.ColorRole.WindowText) == QColor('#00E5FF')
        assert isinstance(card, HudPanel)
        assert not card.grab().isNull()
        restored = ThemeManager(app, manager.template)
        assert restored.current_accent == 'neon'
        restored.apply('light', animate=False)
        app.processEvents()
        assert not card._value_glow.isEnabled()
        assert card.value_label.palette().color(QPalette.ColorRole.WindowText) == QColor('#0E7490')
        restored.set_accent('gold')
        app.processEvents()
        assert not card._value_glow.isEnabled()
        assert card.value_label.palette().color(QPalette.ColorRole.WindowText) == QColor('#172033')
        assert '{{' not in app.styleSheet()
    finally:
        card.close()


def test_glow_layers_only_in_dark_neon(context):
    from charts import ModernSplineChart
    app, manager = context
    chart = ModernSplineChart()
    try:
        for accent, theme, expected in [('blue', 'dark', False), ('neon', 'dark', True), ('neon', 'light', False)]:
            manager.set_accent(accent)
            manager.apply(theme, animate=False)
            chart.plot_trend([0, 1, 2], [1, 2, 3])
            assert any(line.get_label() == '_glow' for line in chart.ax.lines) == expected
            actual = next(line for line in chart.ax.lines if line.get_label() == 'OPS')
            assert list(actual.get_ydata()) == [1, 2, 3]
    finally:
        chart.close()


def test_neon_tokens_keep_status_colors_and_light_text_contrast():
    from config.theme_tokens import tokens_for
    def luminance(hex_color):
        color = QColor(hex_color)
        channels = [color.redF(), color.greenF(), color.blueF()]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
        return sum(a * b for a, b in zip(linear, [.2126, .7152, .0722]))
    for theme in ('dark', 'light'):
        neon, blue = tokens_for(theme, 'neon'), tokens_for(theme, 'blue')
        for role in ('--color-success', '--color-warning', '--color-danger'):
            assert neon[role] == blue[role]
        for text_role in ('--color-kpi', '--color-text-subtle'):
            values = sorted([luminance(neon[text_role]), luminance(neon['--color-panel-top'])])
            assert (values[1] + .05) / (values[0] + .05) >= 4.5


def test_settings_neon_preview_and_cancel(context, tmp_path):
    from controllers.app_controller import AppController
    from database.sqlite_manager import SQLiteManager
    from ui.main_window import MainWindow
    from ui.settings_dialog import SettingsDialog
    app, manager = context
    manager.set_accent('gold')
    window = MainWindow()
    window.theme_manager = manager
    controller = AppController(window, SQLiteManager(tmp_path / 'test.sqlite3'))
    dialog = SettingsDialog(window, controller)
    try:
        dialog.accent.setCurrentIndex(dialog.accent.findData('neon'))
        assert manager.current_accent == 'neon'
        dialog.reject()
        assert manager.current_accent == 'gold'
        assert manager.settings.value(ACCENT_STORAGE_KEY) == 'gold'
    finally:
        dialog.guard.stop()
        dialog.close()
        window.close()
