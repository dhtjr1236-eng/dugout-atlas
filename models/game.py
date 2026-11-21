from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TeamRef:
    id: int
    name: str
    abbreviation: str = ""
    score: int | None = None
    logo_path: str | None = None


@dataclass(slots=True)
class GameSummary:
    game_pk: int
    game_date: str
    status: str
    detailed_status: str
    away: TeamRef
    home: TeamRef
    inning: int | None = None
    inning_state: str = ""
    venue: str = ""

    @property
    def matchup(self) -> str:
        away = self.away.abbreviation or self.away.name
        home = self.home.abbreviation or self.home.name
        return f"{away} vs {home}"


@dataclass(slots=True)
class LineupPlayer:
    id: int
    name: str
    position: str = ""
    batting_order: int | None = None
    game_stats: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GameDetail:
    game_pk: int
    away: TeamRef
    home: TeamRef
    status: str
    balls: int = 0
    strikes: int = 0
    outs: int = 0
    inning: int | None = None
    inning_state: str = ""
    on_first: bool = False
    on_second: bool = False
    on_third: bool = False
    batter: LineupPlayer | None = None
    pitcher: LineupPlayer | None = None
    recent_play: str = ""
    away_lineup: list[LineupPlayer] = field(default_factory=list)
    home_lineup: list[LineupPlayer] = field(default_factory=list)
    away_pitchers: list[LineupPlayer] = field(default_factory=list)
    home_pitchers: list[LineupPlayer] = field(default_factory=list)
    away_hits: int | None = None
    home_hits: int | None = None
    away_errors: int | None = None
    home_errors: int | None = None
    linescore: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
