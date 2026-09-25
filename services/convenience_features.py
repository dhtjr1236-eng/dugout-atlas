from __future__ import annotations

from config.i18n import tr

from typing import Any

from services.favorites_service import FavoritesService


METRIC_TOOLTIPS: dict[str, str] = {
    "AVG": "타율: 안타 ÷ 타수",
    "OBP": "출루율: 타자가 출루한 비율",
    "SLG": "장타율: 타수당 총 루타",
    "OPS": "출루율 + 장타율",
    "HR": "홈런",
    "RBI": "타점",
    "SB": "도루 성공",
    "PA": "타석 수",
    "fWAR": "FanGraphs WAR: 대체선수 대비 기여 승수",
    "bWAR": "Baseball-Reference WAR",
    "wRC+": "조정 득점 생산력. 100이 리그 평균",
    "OPS+": "리그·구장을 보정한 OPS. 100이 평균",
    "ISO": "순수 장타력: SLG - AVG",
    "BABIP": "인플레이 타구 타율",
    "BB%": "볼넷 비율",
    "K%": "삼진 비율",
    "wOBA": "타격 결과별 가중치를 적용한 출루 생산성 지표",
    "Avg EV": "평균 타구 속도",
    "Max EV": "최고 타구 속도",
    "Hard Hit %": "95mph 이상 강한 타구 비율",
    "Barrel %": "배럴 타구 비율",
    "xBA": "Statcast 기대 타율",
    "xSLG": "Statcast 기대 장타율",
    "xwOBA": "Statcast 기대 wOBA",
    "OAA": "Outs Above Average: 평균 수비수 대비 추가 아웃 기여",
    "Runs Prevented": "Statcast 수비 기여의 실점 억제 값",
    "ERA": "9이닝당 자책점",
    "WHIP": "이닝당 허용 출루(볼넷+피안타)",
    "FIP": "수비 영향이 적은 결과 중심 투수 평가 지표",
    "xFIP": "홈런을 평균 HR/FB로 보정한 FIP",
    "ERA+": "리그·구장 보정 ERA. 100이 평균이며 높을수록 좋음",
    "xERA": "Statcast 기대 ERA",
    "Whiff %": "스윙 중 헛스윙 비율",
    "Chase %": "스트라이크존 밖 공에 스윙한 비율",
    "Avg EV Allowed": "허용 타구 평균 타구 속도",
}


def game_snapshot(game: Any) -> tuple[Any, ...]:
    return (
        int(game.away.score) if game.away.score is not None else None,
        int(game.home.score) if game.home.score is not None else None,
        str(game.detailed_status or ""),
        int(game.inning or 0),
        str(game.inning_state or ""),
    )


def game_notification(
    old: tuple[Any, ...],
    new: tuple[Any, ...],
    game: Any,
) -> str | None:
    old_away, old_home, old_status, _, _ = old
    new_away, new_home, new_status, inning, inning_state = new
    away = game.away.abbreviation or game.away.name
    home = game.home.abbreviation or game.home.name

    if (old_away, old_home) != (new_away, new_home):
        return (
            f"{away} {new_away if new_away is not None else '–'} - "
            f"{new_home if new_home is not None else '–'} {home} · "
            f"{inning_state} {inning}"
        ).strip()

    if old_status != new_status:
        return f"{away} vs {home} · {new_status}"

    return None


def install_convenience_features() -> None:
    """
    경기 알림, 선수/팀 즐겨찾기, Compare 지표 툴팁만 설치한다.

    PlayerService / Baseball-Reference / 캐시 정책은 전혀 수정하지 않는다.
    """
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import (
        QApplication,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QPushButton,
        QStyle,
        QSystemTrayIcon,
        QVBoxLayout,
    )

    from ui.compare_view import CompareView
    from ui.main_window import MainWindow

    if getattr(MainWindow, "_convenience_features_installed", False):
        return

    original_main_init = MainWindow.__init__
    original_set_games = MainWindow.set_games
    original_set_game_detail = MainWindow.set_game_detail
    original_show_player = MainWindow.show_player
    original_compare_render = CompareView._render

    def refresh_favorites(self: MainWindow) -> None:
        payload = self._favorites.load()
        self.favorite_list.clear()

        for row in payload["players"]:
            text = f"★ 선수 · {row.get('name', 'Unknown')}"
            if row.get("team"):
                text += f" · {row.get('team')}"
            item = QListWidgetItem(tr(text))
            item.setData(
                Qt.ItemDataRole.UserRole,
                ("player", int(row.get("id", 0) or 0)),
            )
            self.favorite_list.addItem(tr(item))

        for row in payload["teams"]:
            label = row.get("abbreviation") or row.get("name") or "Unknown"
            item = QListWidgetItem(tr(f"★ 팀 · {label}"))
            item.setData(
                Qt.ItemDataRole.UserRole,
                ("team", int(row.get("id", 0) or 0)),
            )
            self.favorite_list.addItem(tr(item))

        player = getattr(self, "_favorite_player_payload", None)
        if player:
            active = self._favorites.is_player(int(player["id"]))
            self.favorite_player_button.setText(
                tr("★ 선수 즐겨찾기 해제" if active else "☆ 현재 선수 저장")
            )

        for side in ("away", "home"):
            team = getattr(self, f"_favorite_{side}_team", None)
            button = getattr(self, f"favorite_{side}_button", None)
            if team and button is not None:
                active = self._favorites.is_team(int(team["id"]))
                prefix = "★" if active else "☆"
                label = team.get("abbreviation") or team.get("name") or side
                button.setText(tr(f"{prefix} {label}"))

    def notify(self: MainWindow, title: str, message: str) -> None:
        from config.preferences import read_preferences
        if not read_preferences()["notifications"]:
            return
        tray = getattr(self, "_notification_tray", None)
        if tray is not None and QSystemTrayIcon.isSystemTrayAvailable():
            tray.showMessage(
                tr(title),
                message,
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )
        else:
            self.statusBar().showMessage(tr(f"{title}: {message}"), 5000)

    def init_main(self: MainWindow) -> None:
        original_main_init(self)

        self._favorites = FavoritesService()
        self._favorite_game_snapshots: dict[int, tuple[Any, ...]] = {}
        self._favorite_player_payload: dict[str, Any] | None = None
        self._favorite_away_team: dict[str, Any] | None = None
        self._favorite_home_team: dict[str, Any] | None = None

        app = QApplication.instance()
        icon: QIcon = self.windowIcon()
        if icon.isNull() and app is not None:
            icon = app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

        self._notification_tray = QSystemTrayIcon(icon, self)
        self._notification_tray.setToolTip(tr("Dugout Atlas 경기 알림"))
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._notification_tray.show()

        left = self.game_list.parentWidget()
        left_layout = left.layout() if left is not None else None
        if left_layout is None:
            return

        box = QGroupBox(tr("즐겨찾기 / 알림"))
        layout = QVBoxLayout(box)

        self.favorite_list = QListWidget()
        self.favorite_list.setMaximumHeight(160)
        layout.addWidget(self.favorite_list)

        self.favorite_player_button = QPushButton(tr("☆ 현재 선수 저장"))
        self.favorite_player_button.setEnabled(False)
        layout.addWidget(self.favorite_player_button)

        team_row = QHBoxLayout()
        self.favorite_away_button = QPushButton(tr("☆ 원정팀"))
        self.favorite_home_button = QPushButton(tr("☆ 홈팀"))
        self.favorite_away_button.setEnabled(False)
        self.favorite_home_button.setEnabled(False)
        team_row.addWidget(self.favorite_away_button)
        team_row.addWidget(self.favorite_home_button)
        layout.addLayout(team_row)

        hint = QLabel(
            tr("즐겨찾기 팀의 점수 또는 경기 상태가 바뀌면 알림을 표시합니다.")
        )
        hint.setWordWrap(True)
        hint.setObjectName("subtitle")
        layout.addWidget(hint)

        left_layout.addWidget(box)

        def toggle_player() -> None:
            payload = self._favorite_player_payload
            if not payload:
                return
            self._favorites.toggle_player(
                int(payload["id"]),
                str(payload["name"]),
                str(payload.get("team", "")),
                str(payload.get("position", "")),
            )
            refresh_favorites(self)

        def toggle_team(side: str) -> None:
            payload = getattr(self, f"_favorite_{side}_team", None)
            if not payload:
                return
            self._favorites.toggle_team(
                int(payload["id"]),
                str(payload["name"]),
                str(payload.get("abbreviation", "")),
            )
            refresh_favorites(self)

        def open_favorite(item: QListWidgetItem) -> None:
            data = item.data(Qt.ItemDataRole.UserRole)
            if (
                isinstance(data, tuple)
                and len(data) == 2
                and data[0] == "player"
                and data[1]
            ):
                self.search_player_selected.emit(int(data[1]))

        self.favorite_player_button.clicked.connect(toggle_player)
        self.favorite_away_button.clicked.connect(lambda: toggle_team("away"))
        self.favorite_home_button.clicked.connect(lambda: toggle_team("home"))
        self.favorite_list.itemDoubleClicked.connect(open_favorite)

        refresh_favorites(self)

    def set_games_with_notifications(
        self: MainWindow,
        games: list[Any],
    ) -> None:
        favorite_teams = (
            self._favorites.team_ids()
            if hasattr(self, "_favorites")
            else set()
        )
        previous = dict(
            getattr(self, "_favorite_game_snapshots", {})
        )

        original_set_games(self, games)

        current: dict[int, tuple[Any, ...]] = {}
        for game in games:
            watched = (
                game.away.id in favorite_teams
                or game.home.id in favorite_teams
            )
            if not watched:
                continue

            snapshot = game_snapshot(game)
            game_pk = int(game.game_pk)
            current[game_pk] = snapshot

            old = previous.get(game_pk)
            if old is not None:
                message = game_notification(old, snapshot, game)
                if message:
                    notify(
                        self,
                        "즐겨찾기 팀 경기 업데이트",
                        message,
                    )

        self._favorite_game_snapshots = current

    def set_game_detail_with_favorites(
        self: MainWindow,
        detail: Any,
    ) -> None:
        original_set_game_detail(self, detail)

        self._favorite_away_team = {
            "id": int(detail.away.id),
            "name": detail.away.name,
            "abbreviation": detail.away.abbreviation,
        }
        self._favorite_home_team = {
            "id": int(detail.home.id),
            "name": detail.home.name,
            "abbreviation": detail.home.abbreviation,
        }

        self.favorite_away_button.setEnabled(True)
        self.favorite_home_button.setEnabled(True)
        refresh_favorites(self)

    def show_player_with_favorite(
        self: MainWindow,
        bundle: Any,
    ) -> None:
        original_show_player(self, bundle)

        profile = bundle.profile
        self._favorite_player_payload = {
            "id": int(profile.id),
            "name": profile.full_name,
            "team": profile.team,
            "position": profile.position,
        }

        self.favorite_player_button.setEnabled(True)
        refresh_favorites(self)

    def compare_render_with_tooltips(self: CompareView) -> None:
        original_compare_render(self)

        for row in range(self.table.rowCount()):
            metric_item = self.table.item(row, 0)
            if metric_item is None:
                continue

            tooltip = METRIC_TOOLTIPS.get(metric_item.data(Qt.ItemDataRole.UserRole) or metric_item.text(), "")
            if not tooltip:
                continue

            for column in range(self.table.columnCount()):
                cell = self.table.item(row, column)
                if cell is not None:
                    cell.setToolTip(tr(tooltip))

    MainWindow.__init__ = init_main  # type: ignore[method-assign]
    MainWindow.set_games = set_games_with_notifications  # type: ignore[method-assign]
    MainWindow.set_game_detail = set_game_detail_with_favorites  # type: ignore[method-assign]
    MainWindow.show_player = show_player_with_favorite  # type: ignore[method-assign]
    CompareView._render = compare_render_with_tooltips  # type: ignore[method-assign]
    MainWindow._convenience_features_installed = True  # type: ignore[attr-defined]
