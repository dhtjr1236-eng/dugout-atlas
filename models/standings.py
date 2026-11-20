from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class StandingRow:
    team_id: int
    team: str
    wins: int
    losses: int
    pct: str
    games_back: str
    division_rank: str = ""
    league_rank: str = ""
    wild_card_rank: str = ""
