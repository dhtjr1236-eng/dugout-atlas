from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import Any, Callable

from database.sqlite_manager import SQLiteManager
from models.player import PlayerBundle, PlayerProfile
from services.bref_service import BaseballReferenceService
from services.fangraphs_service import FanGraphsService
from services.mlb_api import MLBApiService
from services.statcast_service import StatcastService

LOGGER = logging.getLogger(__name__)


class PlayerService:
    """Application-facing player facade.

    Network/pybaseball source failures are isolated so one source does not blank
    the whole player page.
    """

    def __init__(self, db: SQLiteManager, mlb_api: MLBApiService) -> None:
        self.db = db
        self.mlb_api = mlb_api
        self.fangraphs = FanGraphsService(db)
        self.bref = BaseballReferenceService(db)
        self.statcast = StatcastService(db)

    async def search(self, query: str) -> list[dict[str, Any]]:
        return await self.mlb_api.search_people(query)

    async def get_bundle(self, player_id: int, season: int) -> PlayerBundle:
        profile = await self.mlb_api.get_player_profile(player_id)
        self.db.upsert_player(player_id, asdict(profile))
        pitcher = profile.is_pitcher
        group = "pitching" if pitcher else "hitting"

        bundle = PlayerBundle(profile=profile)
        try:
            bundle.basic = await self.mlb_api.get_player_season_stats(
                player_id, season, group
            )
        except Exception as exc:
            bundle.errors.append(f"MLB basic stats: {exc}")

        # pybaseball functions are blocking. Offload each source to a thread.
        tasks: list[tuple[str, Callable[[], Any]]] = []
        if pitcher:
            tasks.extend(
                [
                    (
                        "fangraphs",
                        lambda: self.fangraphs.get_pitcher(
                            player_id, profile.full_name, season
                        ),
                    ),
                    ("bref", lambda: self.bref.get_bwar(player_id, season, True, profile.full_name)),
                    (
                        "statcast",
                        lambda: self.statcast.get_pitcher_metrics(player_id, season),
                    ),
                    (
                        "pitch_table",
                        lambda: self.statcast.get_pitch_arsenal(player_id, season),
                    ),
                    (
                        "history",
                        lambda: self.fangraphs.get_history(
                            player_id,
                            profile.full_name,
                            max(2002, season - 5),
                            season,
                            True,
                        ),
                    ),
                    (
                        "velocity_history",
                        lambda: self.statcast.get_velocity_history(player_id, season),
                    ),
                ]
            )
        else:
            tasks.extend(
                [
                    (
                        "fangraphs",
                        lambda: self.fangraphs.get_batter(
                            player_id, profile.full_name, season
                        ),
                    ),
                    ("bref", lambda: self.bref.get_bwar(player_id, season, False, profile.full_name)),
                    (
                        "statcast",
                        lambda: self.statcast.get_batter_metrics(player_id, season),
                    ),
                    (
                        "defense",
                        lambda: self.statcast.get_defense(
                            player_id, season, profile.position
                        ),
                    ),
                    (
                        "history",
                        lambda: self.fangraphs.get_history(
                            player_id,
                            profile.full_name,
                            max(2002, season - 5),
                            season,
                            False,
                        ),
                    ),
                ]
            )

        results = await asyncio.gather(
            *(asyncio.to_thread(func) for _, func in tasks),
            return_exceptions=True,
        )
        for (name, _), result in zip(tasks, results, strict=True):
            if isinstance(result, Exception):
                LOGGER.exception("Source %s failed for player %s", name, player_id, exc_info=result)
                bundle.errors.append(f"{name}: {result}")
                continue
            setattr(bundle, name, result)
            if isinstance(result, dict):
                source_errors = result.get("_errors")
                if isinstance(source_errors, list):
                    bundle.errors.extend(
                        f"{name}: {message}" for message in source_errors if message
                    )
        return bundle

    def get_fangraphs_trend(
        self,
        player_id: int,
        full_name: str,
        season: int,
        pitcher: bool,
        period: str,
    ) -> list[dict[str, Any]]:
        """Load FanGraphs WAR/wRC+ trend data for the requested granularity."""
        return self.fangraphs.get_period_history(
            player_id, full_name, season, pitcher, period
        )
