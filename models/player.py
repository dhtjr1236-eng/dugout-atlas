from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PlayerProfile:
    id: int
    full_name: str
    team: str = ""
    position: str = ""
    age: int | None = None
    bats: str = ""
    throws: str = ""
    birth_date: str = ""
    primary_number: str = ""

    @property
    def is_pitcher(self) -> bool:
        return self.position.upper() in {"P", "SP", "RP", "TWP"}


@dataclass(slots=True)
class PlayerBundle:
    profile: PlayerProfile
    basic: dict[str, Any] = field(default_factory=dict)
    fangraphs: dict[str, Any] = field(default_factory=dict)
    bref: dict[str, Any] = field(default_factory=dict)
    statcast: dict[str, Any] = field(default_factory=dict)
    defense: dict[str, Any] = field(default_factory=dict)
    pitch_table: list[dict[str, Any]] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    velocity_history: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
