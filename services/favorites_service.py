from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from config.settings import DATA_DIR


class FavoritesService:
    """선수/팀 즐겨찾기를 로컬 JSON으로 저장한다."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or (DATA_DIR / "favorites.json"))
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _default() -> dict[str, list[dict[str, Any]]]:
        return {"players": [], "teams": []}

    @staticmethod
    def _id(row: dict[str, Any]) -> int:
        try:
            return int(row.get("id", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def load(self) -> dict[str, list[dict[str, Any]]]:
        with self._lock:
            if not self.path.exists():
                return self._default()
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return self._default()
            if not isinstance(raw, dict):
                return self._default()
            return {
                "players": raw.get("players", []) if isinstance(raw.get("players"), list) else [],
                "teams": raw.get("teams", []) if isinstance(raw.get("teams"), list) else [],
            }

    def _save(self, payload: dict[str, list[dict[str, Any]]]) -> None:
        temp = self.path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temp.replace(self.path)

    def _toggle(self, bucket: str, item: dict[str, Any]) -> bool:
        item_id = self._id(item)
        if not item_id:
            return False
        with self._lock:
            payload = self.load()
            rows = list(payload[bucket])
            index = next(
                (i for i, row in enumerate(rows) if self._id(row) == item_id),
                None,
            )
            if index is None:
                rows.append(dict(item))
                enabled = True
            else:
                rows.pop(index)
                enabled = False
            payload[bucket] = rows
            self._save(payload)
            return enabled

    def toggle_player(
        self,
        player_id: int,
        name: str,
        team: str = "",
        position: str = "",
    ) -> bool:
        return self._toggle(
            "players",
            {
                "id": int(player_id),
                "name": str(name),
                "team": str(team),
                "position": str(position),
            },
        )

    def toggle_team(
        self,
        team_id: int,
        name: str,
        abbreviation: str = "",
    ) -> bool:
        return self._toggle(
            "teams",
            {
                "id": int(team_id),
                "name": str(name),
                "abbreviation": str(abbreviation),
            },
        )

    def is_player(self, player_id: int) -> bool:
        return any(self._id(row) == int(player_id) for row in self.load()["players"])

    def is_team(self, team_id: int) -> bool:
        return any(self._id(row) == int(team_id) for row in self.load()["teams"])

    def team_ids(self) -> set[int]:
        return {
            self._id(row)
            for row in self.load()["teams"]
            if self._id(row)
        }
