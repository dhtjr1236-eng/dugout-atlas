from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any, Callable

from PyQt6.QtCore import QObject, QTimer

from database.sqlite_manager import SQLiteManager
from models.game import GameDetail, GameSummary
from services.league_service import LeagueService
from services.mlb_api import MLBApiService
from services.player_service import PlayerService
from ui.main_window import MainWindow
from workers.qt_worker import TaskThread

LOGGER = logging.getLogger(__name__)


class AppController(QObject):
    """Coordinates views and service calls without placing I/O on the UI thread."""

    def __init__(self, window: MainWindow, db: SQLiteManager) -> None:
        super().__init__(window)
        self.window = window
        self.db = db
        self.mlb = MLBApiService()
        self.players = PlayerService(db, self.mlb)
        self.league = LeagueService(self.mlb)
        self.season = date.today().year
        self.selected_game_pk: int | None = None
        self.selected_player_id: int | None = None
        self._threads: set[TaskThread] = set()
        self._schedule_busy = False
        self._game_busy = False
        self._player_busy = False
        self._trend_busy = False
        self._pending_trend_period: str | None = None

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(30_000)
        self.refresh_timer.timeout.connect(self.refresh_live)

        self.player_refresh_timer = QTimer(self)
        self.player_refresh_timer.setInterval(300_000)
        self.player_refresh_timer.timeout.connect(self.refresh_selected_player)

        self.window.game_selected.connect(self.select_game)
        self.window.date_changed.connect(self.load_schedule)
        self.window.search_requested.connect(self.search_players)
        self.window.search_player_selected.connect(self.load_player)
        self.window.league_refresh_requested.connect(self.load_league)
        self.window.team_stats_requested.connect(self.load_team_stats)
        self.window.bref_import_requested.connect(self.import_bref_file)
        self.window.player_view.trend_period_changed.connect(self.load_player_trend)

    def start(self) -> None:
        self.load_schedule(date.today().isoformat())
        self.load_league()
        self.refresh_timer.start()
        self.player_refresh_timer.start()

    def _run(
        self,
        task: Callable[[], Any],
        on_success: Callable[[Any], None],
        *,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        thread = TaskThread(task, self)
        self._threads.add(thread)

        def cleanup() -> None:
            self._threads.discard(thread)
            thread.deleteLater()

        thread.succeeded.connect(on_success)
        thread.succeeded.connect(lambda _value: cleanup())
        thread.failed.connect(on_error or self._default_error)
        thread.failed.connect(lambda _message: cleanup())
        thread.start()

    def load_schedule(self, date_text: str) -> None:
        if self._schedule_busy:
            return
        self._schedule_busy = True
        try:
            self.season = int(date_text[:4])
        except ValueError:
            self.season = date.today().year
        self.window.set_busy(f"Loading games for {date_text}…")

        async def task() -> list[GameSummary]:
            games = await self.mlb.get_schedule(date_text)
            team_ids = [team.id for game in games for team in (game.away, game.home)]
            logos = await self.mlb.get_team_logos(team_ids)
            for game in games:
                away_path = logos.get(game.away.id)
                home_path = logos.get(game.home.id)
                game.away.logo_path = str(away_path) if away_path else None
                game.home.logo_path = str(home_path) if home_path else None
            return games

        def success(games: list[GameSummary]) -> None:
            self._schedule_busy = False
            self.window.set_games(games)
            self.window.set_busy(f"{len(games)} games loaded")

        def failure(message: str) -> None:
            self._schedule_busy = False
            self._default_error(message)

        self._run(task, success, on_error=failure)

    def select_game(self, game_pk: int) -> None:
        self.selected_game_pk = game_pk
        self.load_game_detail(game_pk)

    def load_game_detail(self, game_pk: int) -> None:
        if self._game_busy:
            return
        self._game_busy = True
        self.window.set_busy(f"Loading game {game_pk}…")

        async def task() -> GameDetail:
            detail = await self.mlb.get_live_game(game_pk)
            logos = await self.mlb.get_team_logos([detail.away.id, detail.home.id])
            away_path = logos.get(detail.away.id)
            home_path = logos.get(detail.home.id)
            detail.away.logo_path = str(away_path) if away_path else None
            detail.home.logo_path = str(home_path) if home_path else None
            return detail

        def success(detail: GameDetail) -> None:
            self._game_busy = False
            if detail.game_pk and self.selected_game_pk not in (None, detail.game_pk):
                return
            self.window.set_game_detail(detail)
            self.window.set_busy(f"Updated game {game_pk}")

        def failure(message: str) -> None:
            self._game_busy = False
            self._default_error(message)

        self._run(task, success, on_error=failure)

    def refresh_live(self) -> None:
        qdate = self.window.date_edit.date().toString("yyyy-MM-dd")
        self.load_schedule(qdate)
        if self.selected_game_pk:
            self.load_game_detail(self.selected_game_pk)

    def search_players(self, query: str) -> None:
        expected = query.strip()

        async def task() -> tuple[str, list[dict[str, Any]]]:
            return expected, await self.players.search(expected)

        def success(payload: tuple[str, list[dict[str, Any]]]) -> None:
            original, rows = payload
            if self.window.search.text().strip() == original:
                self.window.update_search_results(rows)

        self._run(task, success, on_error=lambda _message: None)

    def load_player(self, player_id: int) -> None:
        if self._player_busy and self.selected_player_id == player_id:
            return
        self.selected_player_id = player_id
        self._player_busy = True
        self.window.show_player_loading(player_id)
        season = self.season

        async def task() -> Any:
            return await self.players.get_bundle(player_id, season)

        def success(bundle: Any) -> None:
            self._player_busy = False
            if self.selected_player_id != player_id:
                return
            self.window.show_player(bundle)
            self.window.set_busy(f"Player data loaded: {bundle.profile.full_name}")
            period = self.window.player_view.current_trend_period
            if period != "yearly" and not bundle.profile.is_pitcher:
                self.load_player_trend(period)

        def failure(message: str) -> None:
            self._player_busy = False
            self._default_error(message)

        self._run(task, success, on_error=failure)

    def refresh_selected_player(self) -> None:
        """Refresh selected-player data so current-season FanGraphs values advance."""
        if self.selected_player_id is not None and not self._player_busy:
            self.load_player(self.selected_player_id)

    def load_player_trend(self, period: str) -> None:
        bundle = self.window.player_view.current_bundle
        if (
            bundle is None
            or bundle.profile.is_pitcher
            or self.selected_player_id != bundle.profile.id
        ):
            return
        if self._trend_busy:
            self._pending_trend_period = period
            self.window.player_view.set_trend_loading(period)
            return

        player_id = bundle.profile.id
        full_name = bundle.profile.full_name
        season = self.season
        self._trend_busy = True
        self._pending_trend_period = None
        self.window.player_view.set_trend_loading(period)

        def run_pending() -> None:
            pending = self._pending_trend_period
            self._pending_trend_period = None
            if pending and pending != period:
                self.load_player_trend(pending)

        def task() -> list[dict[str, Any]]:
            return self.players.get_fangraphs_trend(
                player_id, full_name, season, False, period
            )

        def success(rows: list[dict[str, Any]]) -> None:
            self._trend_busy = False
            if self.selected_player_id == player_id:
                self.window.player_view.set_trend(period, rows)
                self.window.set_busy(
                    f"FanGraphs {period} trend loaded · {len(rows)} periods"
                )
            run_pending()

        def failure(message: str) -> None:
            self._trend_busy = False
            if self.selected_player_id == player_id:
                self.window.player_view.set_trend(period, [])
                self._default_error(message)
            run_pending()

        self._run(task, success, on_error=failure)

    def import_bref_file(self, file_path: str) -> None:
        self.window.set_busy("Importing Baseball-Reference WAR data…")

        def task() -> dict[str, object]:
            return self.players.bref.import_local_file(file_path)

        def success(result: dict[str, object]) -> None:
            batting = int(result.get("batting_rows", 0) or 0)
            pitching = int(result.get("pitching_rows", 0) or 0)
            self.window.set_busy(
                f"B-Ref import complete · batting {batting:,} rows · pitching {pitching:,} rows"
            )
            if self.selected_player_id:
                self.load_player(self.selected_player_id)

        self._run(task, success)

    def load_league(self) -> None:
        season = self.season
        self.window.set_busy(f"Loading {season} standings…")

        async def task() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
            standings, league_stats = await asyncio.gather(
                self.league.standings(season), self.league.league_stats(season)
            )
            return standings, league_stats

        def success(payload: tuple[list[dict[str, Any]], list[dict[str, Any]]]) -> None:
            standings, league_stats = payload
            self.window.league_view.set_standings(standings)
            self.window.league_view.set_league_stats(league_stats)
            self.window.set_busy(f"{season} standings updated")

        self._run(task, success)

    def load_team_stats(self, team_id: int) -> None:
        season = self.season

        async def task() -> dict[str, Any]:
            return await self.league.team_stats(team_id, season)

        self._run(task, self.window.league_view.set_team_stats)

    def _default_error(self, trace: str) -> None:
        LOGGER.error("Worker failed:\n%s", trace)
        last_line = trace.strip().splitlines()[-1] if trace.strip() else "Unknown error"
        self.window.set_busy(last_line)
        self.window.show_error("Dugout Atlas", last_line)
