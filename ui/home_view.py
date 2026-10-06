from __future__ import annotations

from datetime import date
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QWidget, QScrollArea, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QSpinBox, QFrame, QListWidget, QListWidgetItem)
from config.i18n import tr
from services.home_service import HomeSnapshot


class HomeView(QScrollArea):
    """Season-independent entry point with explicitly local data provenance."""
    refresh_requested = pyqtSignal()
    player_selected = pyqtSignal(int, int)
    navigate_requested = pyqtSignal(str, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._snapshot = None
        self._state = 'empty'
        self._schedule_state = 'unknown'
        self._schedule_date = ''
        self._game_count = 0
        self._columns = 0
        body = QWidget()
        body.setMinimumWidth(0)
        self.setWidget(body)
        root = QVBoxLayout(body)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(16)
        self.eyebrow = QLabel('DUGOUT ATLAS  /  SEASON DESK')
        self.eyebrow.setObjectName('homeEyebrow')
        root.addWidget(self.eyebrow)
        self.title = QLabel()
        self.title.setObjectName('homeTitle')
        self.title.setWordWrap(True)
        root.addWidget(self.title)
        self.subtitle = QLabel()
        self.subtitle.setWordWrap(True)
        root.addWidget(self.subtitle)
        self.selection = QGridLayout()
        selection = self.selection
        self.season_label = QLabel()
        self.season = QSpinBox()
        self.season.setRange(1876, date.today().year)
        self.season.setValue(date.today().year)
        self.season.setAccessibleName(tr('Home season'))
        self.refresh = QPushButton()
        selection.addWidget(self.season_label, 0, 0)
        selection.addWidget(self.season, 0, 1)
        selection.addWidget(self.refresh, 0, 3)
        selection.setColumnStretch(2, 1)
        root.addLayout(selection)
        self.schedule = QLabel()
        self.schedule.setWordWrap(True)
        self.schedule.setObjectName('homeNotice')
        root.addWidget(self.schedule)
        self.inventory = QFrame()
        self.inventory.setObjectName('panel')
        self.inventory.setProperty('homeCard', True)
        inventory_layout = QVBoxLayout(self.inventory)
        self.inventory_title = QLabel()
        inventory_layout.addWidget(self.inventory_title)
        self.counts = QLabel()
        self.counts.setWordWrap(True)
        self.counts.setObjectName('homeCounts')
        inventory_layout.addWidget(self.counts)
        self.state = QLabel()
        self.state.setWordWrap(True)
        inventory_layout.addWidget(self.state)
        root.addWidget(self.inventory)
        self.grid = QGridLayout()
        self.grid.setSpacing(12)
        self.cards = []
        self.buttons = {}
        for key, heading, detail in [
            ('player', 'Explore a player', 'Search a player and inspect the selected season.'),
            ('compare', 'Compare seasons and players', 'Open the existing comparison workspace.'),
            ('race', 'Replay the season race', 'Choose two players in Advanced Compare, then open Season Race.'),
            ('standings', 'Review league standings', 'Load standings for the selected season.')]:
            card = QFrame(); card.setObjectName('panel'); card.setProperty('homeCard', True)
            layout = QVBoxLayout(card)
            button = QPushButton(); button.setProperty('homeHeading', heading)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, k=key: self.navigate_requested.emit(k, self.season.value()))
            label = QLabel(); label.setWordWrap(True); label.setProperty('homeDetail', detail)
            layout.addWidget(button); layout.addWidget(label)
            self.cards.append(card); self.buttons[key] = button
        root.addLayout(self.grid)
        self.favorite_heading = QLabel()
        self.favorite_heading.setObjectName('homeSection')
        root.addWidget(self.favorite_heading)
        self.favorite_hint = QLabel(); self.favorite_hint.setWordWrap(True)
        root.addWidget(self.favorite_hint)
        self.favorites = QListWidget()
        self.favorites.setMinimumHeight(140)
        self.favorites.setMaximumHeight(210)
        self.favorites.setWordWrap(True)
        self.favorites.setCursor(Qt.CursorShape.PointingHandCursor)
        self.favorites.itemClicked.connect(self._open_player)
        root.addWidget(self.favorites)
        self.footer = QLabel(); self.footer.setWordWrap(True)
        root.addWidget(self.footer)
        root.addStretch()
        self.refresh.clicked.connect(self.refresh_requested)
        self.season.valueChanged.connect(self._season_changed)
        self._layout_cards(2)
        self.retranslate()

    def _layout_cards(self, columns: int) -> None:
        if self._columns == columns:
            return
        self._columns = columns
        self.selection.setColumnStretch(2, 1 if columns == 2 else 0)
        self.selection.addWidget(self.refresh, 1 if columns == 1 else 0,
                                 0 if columns == 1 else 3, 1, 2 if columns == 1 else 1)
        for i, card in enumerate(self.cards):
            self.grid.addWidget(card, i // columns, i % columns)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1 if columns == 2 else 0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_cards(1 if self.viewport().width() < 660 else 2)

    def _season_changed(self, _value: int) -> None:
        self._snapshot = None
        self.set_state('loading')
        self.refresh_requested.emit()

    def _open_player(self, item: QListWidgetItem) -> None:
        player_id = item.data(Qt.ItemDataRole.UserRole)
        if type(player_id) is int and player_id > 0:
            self.player_selected.emit(player_id, self.season.value())

    def set_state(self, state: str) -> None:
        self._state = state
        self.refresh.setEnabled(state != 'loading')
        self._render()

    def set_snapshot(self, snapshot: HomeSnapshot) -> None:
        if snapshot.season != self.season.value():
            return
        self._snapshot = snapshot
        self.set_state('ready' if snapshot.record_count else 'empty')

    def set_schedule_state(self, state: str, date_text: str = '', count: int = 0) -> None:
        self._schedule_state, self._schedule_date, self._game_count = state, date_text, count
        self._render()

    def retranslate(self) -> None:
        self.title.setText(tr('A home for every part of the season'))
        self.subtitle.setText(tr('No game today? Revisit a season, follow a favorite, or start a comparison.'))
        self.season_label.setText(tr('Season to explore'))
        self.refresh.setText(tr('Refresh local overview'))
        self.inventory_title.setText(tr('LOCAL LIBRARY · selected season'))
        self.favorite_heading.setText(tr('Your favorite players'))
        self.favorite_hint.setText(tr('Click a player to open this season. Add favorites from a player profile.'))
        self.footer.setText(tr('Overview uses local records only. Opening an analysis may request fresh data. Missing statistics remain missing.'))
        for card in self.cards:
            for button in card.findChildren(QPushButton):
                button.setText(tr(button.property('homeHeading')) + '  →')
            for label in card.findChildren(QLabel):
                label.setText(tr(label.property('homeDetail')))
        self._render()

    def _render(self) -> None:
        texts = {'unknown': 'Schedule has not been checked.', 'loading': 'Checking the selected date…',
                 'empty': 'No games on this date. This does not mean the season has ended.',
                 'ready': 'Games are available. Open Gameday from the tabs.',
                 'error': 'Schedule unavailable. Check your connection; local browsing is still available.'}
        self.schedule.setText((self._schedule_date + '  ·  ' if self._schedule_date else '') + tr(texts[self._schedule_state]))
        snapshot = self._snapshot
        self.counts.setText(tr('Players') + f'  {snapshot.player_count if snapshot else "—"}     /     ' +
                            tr('Sources') + f'  {snapshot.source_count if snapshot else "—"}     /     ' +
                            tr('Cached records') + f'  {snapshot.record_count if snapshot else "—"}')
        if self._state == 'loading': message = tr('Reading your local library…')
        elif self._state == 'error': message = tr('Could not read local data. Previous results are retained. Try refreshing.')
        elif self._state == 'empty': message = tr('No cached statistics for this season yet. Open a player or standings to begin.')
        else: message = tr('Last cache write (UTC)') + ': ' + (snapshot.updated_at if snapshot else '—')
        self.state.setText(message)
        self.favorites.clear()
        for row in snapshot.favorites if snapshot else ():
            item = QListWidgetItem(f"★  {row['name']}" + (f"   ·   {row['team']}" if row['team'] else ''))
            item.setData(Qt.ItemDataRole.UserRole, row['id'])
            self.favorites.addItem(item)
        if not self.favorites.count():
            item = QListWidgetItem(tr('No favorites to display. Search for a player to get started.'))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.favorites.addItem(item)
