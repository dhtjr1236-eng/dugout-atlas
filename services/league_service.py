from __future__ import annotations

from typing import Any

from services.mlb_api import MLBApiService


class LeagueService:
    def __init__(self, mlb_api: MLBApiService) -> None:
        self.mlb_api = mlb_api

    async def standings(self, season: int) -> list[dict[str, Any]]:
        return await self.mlb_api.get_standings(season)

    async def wild_card(self, season: int) -> list[dict[str, Any]]:
        # The Stats API includes wildCardRank in regular-season standings.
        rows = await self.mlb_api.get_standings(season)
        return sorted(
            [row for row in rows if row.get("wild_card_rank")],
            key=lambda row: (
                row.get("league", ""),
                int(row.get("wild_card_rank") or 999),
            ),
        )

    async def league_stats(self, season: int) -> list[dict[str, Any]]:
        return await self.mlb_api.get_league_team_stats(season)

    async def team_stats(self, team_id: int, season: int) -> dict[str, Any]:
        return await self.mlb_api.get_team_season_stats(team_id, season)
