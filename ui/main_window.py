from __future__ import annotations

from PyQt6.QtCore import QDate, QUrl, QStringListModel, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCompleter,
    QDateEdit,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from config.settings import SETTINGS
from models.game import GameDetail, GameSummary
from models.player import PlayerBundle
from ui.compare_view import CompareView
from ui.game_view import GameView
from ui.league_view import LeagueView
from ui.lineup_view import LineupView
from ui.player_view import PlayerView


class MainWindow(QMainWindow):
    game_selected = pyqtSignal(int)
    date_changed = pyqtSignal(str)
    search_requested = pyqtSignal(str)
    search_player_selected = pyqtSignal(int)
    league_refresh_requested = pyqtSignal()
    team_stats_requested = pyqtSignal(int)
    bref_import_requested = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{SETTINGS.app_name} v{SETTINGS.app_version}")
        self.resize(1440, 900)
        self._games: list[GameSummary] = []
        self._search_map: dict[str, int] = {}

        central = QWidget()
        root = QVBoxLayout(central)
        self.setCentralWidget(central)

        top = QHBoxLayout()
        title = QLabel(SETTINGS.app_name)
        title.setObjectName("title")
        top.addWidget(title)
        top.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search player (e.g. Judge)")
        self.search.setMinimumWidth(320)
        self.search_model = QStringListModel(self)
        self.completer = QCompleter(self.search_model, self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.search.setCompleter(self.completer)
        top.addWidget(self.search)
        self.theme_button = QPushButton("Light")
        self.theme_button.setObjectName("themeToggle")
        self.theme_button.setMinimumWidth(64)
        self.theme_button.setToolTip("Light Theme로 전환")
        self.theme_button.setAccessibleName("Light Theme로 전환")
        self.theme_button.setAccessibleDescription("Dugout Atlas 화면 테마 전환 버튼")
        top.addWidget(self.theme_button)
        self.bref_download_button = QPushButton("B-Ref 다운로드")
        self.bref_download_button.setToolTip(
            "Open Baseball-Reference official WAR downloads in your normal browser."
        )
        self.bref_import_button = QPushButton("B-Ref 파일 가져오기")
        self.bref_import_button.setToolTip(
            "Import an official war_archive ZIP or war_daily_bat/pitch TXT/CSV file."
        )
        top.addWidget(self.bref_download_button)
        top.addWidget(self.bref_import_button)
        root.addLayout(top)

        splitter = QSplitter()
        root.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        date_row = QHBoxLayout()
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.today_button = QPushButton("Today")
        date_row.addWidget(self.date_edit)
        date_row.addWidget(self.today_button)
        left_layout.addLayout(date_row)
        left_layout.addWidget(QLabel("Games"))
        self.game_list = QListWidget()
        left_layout.addWidget(self.game_list, 1)
        splitter.addWidget(left)

        self.tabs = QTabWidget()
        self.game_view = GameView()
        self.lineup_view = LineupView()
        self.player_view = PlayerView()
        self.compare_view = CompareView()
        self.league_view = LeagueView()
        self.tabs.addTab(self.game_view, "Gameday")
        self.tabs.addTab(self.lineup_view, "Lineups")
        self.tabs.addTab(self.player_view, "Player")
        self.tabs.addTab(self.compare_view, "Compare")
        self.tabs.addTab(self.league_view, "Standings")
        splitter.addWidget(self.tabs)
        splitter.setSizes([330, 1110])

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

        self.game_list.currentRowChanged.connect(self._on_game_row)
        self.date_edit.dateChanged.connect(self._on_date_changed)
        self.today_button.clicked.connect(lambda: self.date_edit.setDate(QDate.currentDate()))
        self.search.textChanged.connect(self._debounce_search)
        self.completer.activated[str].connect(self._on_completion)
        self.search.returnPressed.connect(self._on_search_enter)
        self.game_view.player_clicked.connect(self.search_player_selected)
        self.lineup_view.player_clicked.connect(self.search_player_selected)
        self.league_view.refresh_requested.connect(self.league_refresh_requested)
        self.league_view.team_selected.connect(self.team_stats_requested)
        self.bref_download_button.clicked.connect(self._open_bref_downloads)
        self.bref_import_button.clicked.connect(self._choose_bref_import)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(350)
        self._search_timer.timeout.connect(self._emit_search)

    def set_games(self, games: list[GameSummary]) -> None:
        current_pk = None
        current_row = self.game_list.currentRow()
        if 0 <= current_row < len(self._games):
            current_pk = self._games[current_row].game_pk
        self._games = games
        self.game_list.clear()
        select_row = -1
        for index, game in enumerate(games):
            away_score = "–" if game.away.score is None else str(game.away.score)
            home_score = "–" if game.home.score is None else str(game.home.score)
            inning = f" | {game.inning_state} {game.inning}" if game.inning else ""
            text = (
                f"{game.matchup}\n"
                f"{game.away.abbreviation or game.away.name} {away_score}   "
                f"{game.home.abbreviation or game.home.name} {home_score}\n"
                f"{game.detailed_status}{inning}"
            )
            item = QListWidgetItem(text)
            item.setToolTip(game.venue)
            self.game_list.addItem(item)
            if game.game_pk == current_pk:
                select_row = index
        if games:
            self.game_list.setCurrentRow(select_row if select_row >= 0 else 0)
        else:
            self.statusBar().showMessage("No MLB games found for this date")

    def set_game_detail(self, detail: GameDetail) -> None:
        self.game_view.set_game(detail)
        self.lineup_view.set_game(detail)

    def update_search_results(self, rows: list[dict[str, object]]) -> None:
        self._search_map = {}
        labels: list[str] = []
        for row in rows:
            name = str(row.get("name", ""))
            team = str(row.get("team", ""))
            position = str(row.get("position", ""))
            label = name
            if team or position:
                label = f"{name} — {team} {position}".strip()
            self._search_map[label] = int(row.get("id", 0))
            labels.append(label)
        self.search_model.setStringList(labels)
        if labels and self.search.hasFocus():
            self.completer.complete()

    def show_player(self, bundle: PlayerBundle) -> None:
        self.player_view.set_bundle(bundle)
        self.tabs.setCurrentWidget(self.player_view)

    def show_player_loading(self, player_id: int) -> None:
        self.player_view.set_loading(player_id)
        self.tabs.setCurrentWidget(self.player_view)

    def show_error(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def set_busy(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def _open_bref_downloads(self) -> None:
        QDesktopServices.openUrl(QUrl("https://www.baseball-reference.com/data/"))

    def _choose_bref_import(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Import Baseball-Reference WAR data",
            "",
            "B-Ref WAR files (*.zip *.txt *.csv);;ZIP files (*.zip);;Text/CSV (*.txt *.csv);;All files (*.*)",
        )
        if path:
            self.bref_import_requested.emit(path)

    def _on_game_row(self, row: int) -> None:
        if 0 <= row < len(self._games):
            self.game_selected.emit(self._games[row].game_pk)

    def _on_date_changed(self, qdate: QDate) -> None:
        self.date_changed.emit(qdate.toString("yyyy-MM-dd"))

    def _debounce_search(self, _text: str) -> None:
        self._search_timer.start()

    def _emit_search(self) -> None:
        text = self.search.text().strip()
        if len(text) >= 2:
            self.search_requested.emit(text)
        else:
            self.update_search_results([])

    def _on_completion(self, label: str) -> None:
        player_id = self._search_map.get(label)
        if player_id:
            self.search_player_selected.emit(player_id)

    def _on_search_enter(self) -> None:
        text = self.search.text().strip().casefold()
        for label, player_id in self._search_map.items():
            if label.casefold().startswith(text):
                self.search_player_selected.emit(player_id)
                return
