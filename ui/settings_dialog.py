from __future__ import annotations

import json
import sqlite3

from PyQt6.QtCore import QTimer, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (QComboBox, QCheckBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QTabWidget, QVBoxLayout, QWidget, QPlainTextEdit)

from config.i18n import LANGUAGES, set_language, tr, translate_widgets
from config.preferences import read_preferences, save_preferences
from config.settings import RUNTIME_ROOT
from services.settings_service import SOURCES, clear_cache, copy_data_location, diagnostics, export_diagnostics


class SettingsDialog(QDialog):
    def __init__(self, window, controller):
        super().__init__(window)
        self.window, self.controller = window, controller
        self.values = read_preferences()
        self.needs_refresh = False
        self.setWindowTitle(tr('Settings'))
        self.resize(720, 500)
        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs)
        general = QWidget()
        form = QFormLayout(general)
        self.refresh = self._spin(self.values['refresh_seconds'], 15, 3600)
        self.player_refresh = self._spin(self.values['player_refresh_seconds'], 60, 3600)
        self.notifications = QCheckBox(tr('Game notifications'))
        self.notifications.setChecked(self.values['notifications'])
        self.theme = QComboBox()
        for key in ('light', 'dark'):
            self.theme.addItem(tr(key.title()), key)
        self.theme.setCurrentIndex(self.theme.findData(window.theme_manager.current_theme))
        self.font = self._spin(self.values['font_scale'], 80, 160)
        self.font.setSingleStep(10)
        self.language = QComboBox()
        for code, label in LANGUAGES.items():
            self.language.addItem(label, code)
        self.language.setCurrentIndex(self.language.findData(self.values['language']))
        form.addRow(tr('Game refresh interval (seconds)'), self.refresh)
        form.addRow(tr('Player refresh interval (seconds)'), self.player_refresh)
        form.addRow(tr('Theme'), self.theme)
        form.addRow(tr('Font size (%)'), self.font)
        form.addRow(tr('App language'), self.language)
        form.addRow(self.notifications)
        note = QLabel(tr('Interface labels and built-in explanations switch immediately. Player names, metric abbreviations and provider text are preserved.'))
        note.setWordWrap(True)
        form.addRow(note)
        tabs.addTab(general, tr('General'))

        data = QWidget()
        layout = QVBoxLayout(data)
        layout.addWidget(QLabel(tr('Data location')))
        self.location = QLineEdit(str(RUNTIME_ROOT))
        self.location.setReadOnly(True)
        layout.addWidget(self.location)
        row = QHBoxLayout()
        self.choose = QPushButton(tr('Choose folder'))
        self.choose.clicked.connect(self._choose_folder)
        row.addWidget(self.choose)
        open_button = QPushButton(tr('Open folder'))
        open_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(RUNTIME_ROOT))))
        row.addWidget(open_button)
        layout.addLayout(row)
        note = QLabel(tr('Data location changes apply after restarting the app. Existing data will be copied; the old folder is retained.'))
        note.setWordWrap(True)
        layout.addWidget(note)
        self.clear = QPushButton(tr('Clear cache'))
        self.clear.clicked.connect(self._clear_cache)
        layout.addWidget(self.clear)
        self.export = QPushButton(tr('Export diagnostics'))
        self.export.clicked.connect(self._export)
        layout.addWidget(QLabel(tr('Refresh source')))
        row = QHBoxLayout()
        self.source = QComboBox()
        self.source.addItems(list(SOURCES))
        row.addWidget(self.source)
        self.reload = QPushButton(tr('Refresh now'))
        self.reload.clicked.connect(self._reload_source)
        row.addWidget(self.reload)
        layout.addLayout(row)
        layout.addStretch()
        tabs.addTab(data, tr('Data'))
        diagnostic_page = QWidget()
        diagnostic_layout = QVBoxLayout(diagnostic_page)
        report = QPlainTextEdit()
        report.setReadOnly(True)
        report.setPlainText(json.dumps(diagnostics(controller.db, self.values), ensure_ascii=False, indent=2))
        diagnostic_layout.addWidget(report)
        diagnostic_layout.addWidget(self.export)
        tabs.addTab(diagnostic_page, tr('Diagnostics'))
        self.status = QLabel('')
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        buttons = QDialogButtonBox()
        self.save_button = buttons.addButton(tr('Save'), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(tr('Cancel'), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.guard = QTimer(self)
        self.guard.timeout.connect(self._update_busy)
        self.guard.start(300)
        self._update_busy()

    @staticmethod
    def _spin(value, low, high):
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setValue(value)
        return spin

    def _update_busy(self):
        busy = bool(self.controller._threads)
        for button in (self.choose, self.clear, self.export, self.reload, self.save_button):
            button.setEnabled(not busy)
        if busy:
            self.status.setText(tr('Waiting for active requests to finish.'))
        elif self.status.text() == tr('Waiting for active requests to finish.'):
            self.status.clear()

    def _choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, tr('Choose folder'), self.location.text())
        if path:
            self.location.setText(path)

    def _clear_cache(self):
        if self.controller._threads:
            return
        answer = QMessageBox.question(self, tr('Clear cache'), tr('Clear downloaded caches? Imported B-Ref files and favorites will be kept.'))
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            clear_cache(self.controller.db)
            self.controller.players.bref._daily_source.clear()
            self.status.setText(tr('Cache cleared.'))
        except (OSError, sqlite3.Error):
            self._failed()

    def _reload_source(self):
        if self.controller._threads:
            return
        try:
            clear_cache(self.controller.db, self.source.currentText())
            if self.source.currentText() == 'Baseball-Reference':
                self.controller.players.bref._daily_source.clear()
            self.needs_refresh = True
            self.status.setText(tr('Source cache cleared. Selected player and game data will refresh after closing Settings.'))
            if self.source.currentText() != 'MLB' and self.controller.selected_player_id is None:
                self.status.setText(tr('No active player: this source will refresh on the next player lookup.'))
        except (OSError, ValueError, sqlite3.Error):
            self._failed()

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, tr('Export diagnostics'), 'dugout-atlas-diagnostics.json', 'JSON (*.json)')
        if path:
            try:
                export_diagnostics(path, self.controller.db, read_preferences())
                self.status.setText(tr('Diagnostics saved.'))
            except (OSError, sqlite3.Error):
                self._failed()

    def _failed(self):
        QMessageBox.warning(self, tr('Settings'), tr('Operation failed. Check folder permissions and try again.'))

    def _save(self):
        if self.controller._threads:
            return
        values = {
            'refresh_seconds': self.refresh.value(),
            'player_refresh_seconds': self.player_refresh.value(),
            'font_scale': self.font.value(), 'notifications': self.notifications.isChecked(),
            'language': self.language.currentData(),
            'data_root': self.values['data_root'],
        }
        try:
            if self.location.text() != str(RUNTIME_ROOT):
                values['data_root'] = copy_data_location(self.location.text(), self.controller.db)
            save_preferences(values)
        except (OSError, ValueError, sqlite3.Error) as exc:
            if isinstance(exc, ValueError):
                QMessageBox.warning(self, tr('Settings'), tr(str(exc)))
            else:
                self._failed()
            return
        manager = self.window.theme_manager
        theme = self.theme.currentData()
        manager.settings.setValue('dugout-atlas-theme', theme)
        manager.settings.sync()
        manager.font_scale = values['font_scale']
        set_language(values['language'])
        manager.apply(theme, animate=False)
        translate_widgets(self.window)
        self.window.set_busy(tr('Settings saved.'))
        self.accept()


def open_settings(window, controller):
    controller.refresh_timer.stop()
    controller.player_refresh_timer.stop()
    dialog = SettingsDialog(window, controller)
    try:
        dialog.exec()
    finally:
        controller.apply_preferences()
        if dialog.needs_refresh:
            controller._refresh_requested()
        dialog.deleteLater()
