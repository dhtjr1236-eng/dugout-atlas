from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from config.settings import DB_PATH, SCHEMA_PATH, ensure_runtime_dirs

LOGGER = logging.getLogger(__name__)


class SQLiteManager:
    """Thread-safe-by-connection SQLite access.

    Each method opens a short-lived connection, which avoids sharing sqlite3
    connection objects across Qt worker threads.
    """

    def __init__(self, db_path: Path = DB_PATH, schema_path: Path = SCHEMA_PATH) -> None:
        ensure_runtime_dirs()
        self.db_path = Path(db_path)
        self.schema_path = Path(schema_path)
        self.initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        schema = self.schema_path.read_text(encoding="utf-8")
        with self.connection() as connection:
            connection.executescript(schema)

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _is_fresh(updated_at: str, ttl_days: float) -> bool:
        try:
            stamp = datetime.fromisoformat(updated_at)
        except ValueError:
            return False
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=UTC)
        return datetime.now(UTC) - stamp < timedelta(days=ttl_days)

    def get_player_stats(
        self,
        player_id: int,
        source: str,
        season: int,
        role: str,
        ttl_days: float,
    ) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT data_json, updated_at FROM player_stats
                WHERE player_id=? AND source=? AND season=? AND role=?
                """,
                (player_id, source, season, role),
            ).fetchone()
        if not row or not self._is_fresh(row["updated_at"], ttl_days):
            return None
        try:
            return json.loads(row["data_json"])
        except json.JSONDecodeError:
            LOGGER.warning("Invalid cached JSON for player %s/%s", player_id, source)
            return None

    def delete_player_stats_source(self, source: str) -> int:
        """Delete cached player-stat rows for one logical source."""
        with self.connection() as connection:
            cursor = connection.execute(
                "DELETE FROM player_stats WHERE source=?", (source,)
            )
            return int(cursor.rowcount or 0)

    def set_player_stats(
        self,
        player_id: int,
        source: str,
        season: int,
        role: str,
        data: dict[str, Any],
    ) -> None:
        payload = json.dumps(data, ensure_ascii=False, default=str)
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO player_stats(player_id, source, season, role, data_json, updated_at)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(player_id, source, season, role) DO UPDATE SET
                    data_json=excluded.data_json,
                    updated_at=excluded.updated_at
                """,
                (player_id, source, season, role, payload, self._now()),
            )

    def set_pitch_stats(
        self,
        player_id: int,
        season: int,
        rows: list[dict[str, Any]],
    ) -> None:
        with self.connection() as connection:
            for row in rows:
                pitch_type = str(row.get("pitch_type") or "Unknown")
                connection.execute(
                    """
                    INSERT INTO pitch_stats(player_id, season, pitch_type, data_json, updated_at)
                    VALUES(?,?,?,?,?)
                    ON CONFLICT(player_id, season, pitch_type) DO UPDATE SET
                        data_json=excluded.data_json,
                        updated_at=excluded.updated_at
                    """,
                    (
                        player_id,
                        season,
                        pitch_type,
                        json.dumps(row, ensure_ascii=False, default=str),
                        self._now(),
                    ),
                )

    def get_pitch_stats(
        self, player_id: int, season: int, ttl_days: float
    ) -> list[dict[str, Any]] | None:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT data_json, updated_at FROM pitch_stats
                WHERE player_id=? AND season=? ORDER BY pitch_type
                """,
                (player_id, season),
            ).fetchall()
        if not rows or any(
            not self._is_fresh(row["updated_at"], ttl_days) for row in rows
        ):
            return None
        result: list[dict[str, Any]] = []
        for row in rows:
            try:
                result.append(json.loads(row["data_json"]))
            except json.JSONDecodeError:
                return None
        return result

    def upsert_player(self, player_id: int, profile: dict[str, Any]) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO players(player_id, full_name, team, position, profile_json, updated_at)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(player_id) DO UPDATE SET
                    full_name=excluded.full_name,
                    team=excluded.team,
                    position=excluded.position,
                    profile_json=excluded.profile_json,
                    updated_at=excluded.updated_at
                """,
                (
                    player_id,
                    profile.get("full_name", ""),
                    profile.get("team", ""),
                    profile.get("position", ""),
                    json.dumps(profile, ensure_ascii=False, default=str),
                    self._now(),
                ),
            )

    def cache_game(self, game_pk: int, game_date: str, status: str, data: dict[str, Any]) -> None:
        """Persist game snapshots for history only; live reads never use this cache."""
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO games(game_pk, game_date, status, data_json, updated_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(game_pk) DO UPDATE SET
                    status=excluded.status,
                    data_json=excluded.data_json,
                    updated_at=excluded.updated_at
                """,
                (
                    game_pk,
                    game_date,
                    status,
                    json.dumps(data, ensure_ascii=False, default=str),
                    self._now(),
                ),
            )

    def purge_expired(self, ttl_days: int) -> None:
        cutoff = (datetime.now(UTC) - timedelta(days=ttl_days)).isoformat()
        with self.connection() as connection:
            connection.execute("DELETE FROM player_stats WHERE updated_at < ?", (cutoff,))
            connection.execute("DELETE FROM pitch_stats WHERE updated_at < ?", (cutoff,))
