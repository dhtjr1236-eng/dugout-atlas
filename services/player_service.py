from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, Callable

import pandas as pd

from database.sqlite_manager import SQLiteManager
from models.player import PlayerBundle, PlayerProfile
from services.bref_service import BaseballReferenceService
from services.fangraphs_service import FanGraphsService
from services.freshness import source_ttl_days
from services.mlb_api import MLBApiService
from services.statcast_service import PITCH_NAMES, StatcastService

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

    def get_pitcher_statcast_period(
        self, player_id: int, season: int, period: str
    ) -> dict[str, Any]:
        """Return pitcher Statcast metrics/arsenal for year, latest month or latest day.

        Monthly and Daily are anchored to the pitcher's latest Statcast appearance in
        the selected season, so an off-day does not produce an artificial empty panel.
        Exact period aggregates are calculated from Baseball Savant pitch-level rows.
        """
        period = period.lower().strip()
        if period not in {"yearly", "monthly", "daily"}:
            raise ValueError(f"Unsupported Statcast period: {period}")

        if period == "yearly":
            return {
                "period": "yearly",
                "label": str(season),
                "statcast": self.statcast.get_pitcher_metrics(player_id, season),
                "pitch_table": self.statcast.get_pitch_arsenal(player_id, season),
                "velocity_history": self.statcast.get_velocity_history(player_id, season),
            }

        cache_group = f"pitcher_period_{period}"
        cached = self.db.get_player_stats(
            player_id,
            "statcast_pitcher_period_v1",
            season,
            cache_group,
            source_ttl_days(season, savant=True),
        )
        if cached:
            return cached

        pb = self.statcast._pybaseball()
        start, end = self.statcast.season_dates(season)
        frame = pb.statcast_pitcher(start, end, int(player_id))
        if frame is None or frame.empty:
            return {
                "period": period,
                "label": "No Statcast appearances",
                "statcast": {},
                "pitch_table": [],
                "velocity_history": [],
            }

        work = frame.copy()
        work["game_date"] = pd.to_datetime(work.get("game_date"), errors="coerce")
        work = work.dropna(subset=["game_date"])
        if work.empty:
            return {
                "period": period,
                "label": "No dated Statcast appearances",
                "statcast": {},
                "pitch_table": [],
                "velocity_history": [],
            }

        latest = work["game_date"].max()
        if period == "monthly":
            filtered = work[
                (work["game_date"].dt.year == int(latest.year))
                & (work["game_date"].dt.month == int(latest.month))
            ].copy()
            label = latest.strftime("%Y-%m")
        else:
            filtered = work[work["game_date"].dt.normalize() == latest.normalize()].copy()
            label = latest.strftime("%Y-%m-%d")

        statcast = self.statcast._aggregate_pitcher(filtered)
        statcast["_source"] = {
            "name": "Baseball Savant Statcast pitch-level data",
            "url": "https://baseballsavant.mlb.com/statcast_search",
            "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        statcast["_period"] = label

        pitch_table = self._pitch_arsenal_from_frame(filtered)
        velocity_history = self._velocity_from_frame(filtered, period)
        result = {
            "period": period,
            "label": label,
            "statcast": statcast,
            "pitch_table": pitch_table,
            "velocity_history": velocity_history,
        }
        self.db.set_player_stats(
            player_id,
            "statcast_pitcher_period_v1",
            season,
            cache_group,
            result,
        )
        return result

    def _pitch_arsenal_from_frame(self, frame: pd.DataFrame) -> list[dict[str, Any]]:
        if frame is None or frame.empty or "pitch_type" not in frame.columns:
            return []
        total = len(frame)
        rows: list[dict[str, Any]] = []
        for pitch_code, group in frame.dropna(subset=["pitch_type"]).groupby("pitch_type"):
            velo = pd.to_numeric(group.get("release_speed"), errors="coerce")
            spin = pd.to_numeric(group.get("release_spin_rate"), errors="coerce")
            delta = pd.to_numeric(group.get("delta_run_exp"), errors="coerce")
            rows.append(
                {
                    "pitch_type": PITCH_NAMES.get(str(pitch_code), str(pitch_code)),
                    "pitch_code": str(pitch_code),
                    "Usage %": float(len(group) / total * 100) if total else None,
                    "Avg Velocity": float(velo.mean()) if velo.notna().any() else None,
                    "Max Velocity": float(velo.max()) if velo.notna().any() else None,
                    "Spin Rate": float(spin.mean()) if spin.notna().any() else None,
                    "Run Value": float(-delta.sum()) if delta.notna().any() else None,
                    "Whiff %": self.statcast._pitch_whiff_percent(group),
                }
            )
        rows.sort(key=lambda row: float(row.get("Usage %") or 0), reverse=True)
        return rows

    @staticmethod
    def _velocity_from_frame(frame: pd.DataFrame, period: str) -> list[dict[str, Any]]:
        if frame is None or frame.empty or "release_speed" not in frame.columns:
            return []
        work = frame.copy()
        work["release_speed"] = pd.to_numeric(work["release_speed"], errors="coerce")
        work["game_date"] = pd.to_datetime(work.get("game_date"), errors="coerce")
        work = work.dropna(subset=["release_speed", "game_date"])
        if work.empty:
            return []

        pitch_name = "All Pitches"
        if "pitch_type" in work.columns:
            fastballs = work[work["pitch_type"].astype(str).isin({"FF", "SI", "FC"})]
            if not fastballs.empty:
                counts = fastballs["pitch_type"].astype(str).value_counts()
                primary_code = str(counts.index[0])
                work = fastballs[fastballs["pitch_type"].astype(str) == primary_code].copy()
                pitch_name = PITCH_NAMES.get(primary_code, primary_code)

        if period == "monthly":
            work["period_key"] = work["game_date"].dt.strftime("%m-%d")
        else:
            work["period_key"] = work["game_date"].dt.strftime("%Y-%m-%d")
        grouped = work.groupby("period_key", sort=True)["release_speed"].agg(["mean", "count"])
        return [
            {
                "Period": str(key),
                "Avg Velocity": float(row["mean"]),
                "Pitches": int(row["count"]),
                "Pitch": pitch_name,
            }
            for key, row in grouped.iterrows()
            if pd.notna(row["mean"])
        ]
