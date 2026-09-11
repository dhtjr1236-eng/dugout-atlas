from __future__ import annotations

import importlib
import logging
from datetime import UTC, date, datetime
from io import StringIO
from typing import Any
from urllib.parse import urlencode

import numpy as np
import pandas as pd

from cache.json_cache import JsonCache
from config.settings import SETTINGS
from database.sqlite_manager import SQLiteManager
from services.dataframe_utils import first_existing, numeric, row_to_dict
from services.base_http import sync_get_text
from services.freshness import source_ttl_days

LOGGER = logging.getLogger(__name__)

PITCH_NAMES = {
    "FF": "Four-Seam Fastball",
    "SI": "Sinker",
    "FC": "Cutter",
    "SL": "Slider",
    "ST": "Sweeper",
    "CU": "Curveball",
    "KC": "Knuckle Curve",
    "CH": "Changeup",
    "FS": "Splitter",
    "FO": "Forkball",
    "SC": "Screwball",
    "KN": "Knuckleball",
    "EP": "Eephus",
}

SWING_DESCRIPTIONS = {
    "swinging_strike",
    "swinging_strike_blocked",
    "foul",
    "foul_tip",
    "hit_into_play",
    "hit_into_play_no_out",
    "hit_into_play_score",
    "missed_bunt",
    "foul_bunt",
}
WHIFF_DESCRIPTIONS = {"swinging_strike", "swinging_strike_blocked", "missed_bunt"}


class StatcastService:
    def __init__(self, db: SQLiteManager) -> None:
        self.db = db
        self.json_cache = JsonCache()

    @staticmethod
    def _pybaseball() -> Any:
        try:
            return importlib.import_module("pybaseball")
        except ImportError as exc:
            raise RuntimeError(
                "pybaseball is not installed. Run install.bat or pip install -r requirements.txt"
            ) from exc

    @staticmethod
    def season_dates(season: int) -> tuple[str, str]:
        current = date.today()
        start = f"{season}-03-01"
        if season == current.year:
            end = current.isoformat()
        else:
            end = f"{season}-11-30"
        return start, end


    @staticmethod
    def _percent_points(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            text = value.strip()
            if text.endswith("%"):
                text = text[:-1]
            try:
                value = float(text)
            except ValueError:
                return value
        try:
            number = float(value)
        except (TypeError, ValueError):
            return value
        return number * 100.0 if 0 <= abs(number) <= 1.0 else number

    def get_batter_metrics(self, player_id: int, season: int) -> dict[str, Any]:
        cached = self.db.get_player_stats(
            player_id,
            "statcast_batter_v5",
            season,
            "batter",
            source_ttl_days(season, savant=True),
        )
        if cached:
            return cached

        pb = self._pybaseball()
        start, end = self.season_dates(season)
        frame = pb.statcast_batter(start, end, int(player_id))
        result = self._aggregate_batter(frame)
        sources: list[dict[str, str]] = []

        # Use Savant's own contact-quality leaderboard for the headline EV,
        # Hard-Hit, Barrel and Sweet-Spot rates. These are the exact season
        # leaderboard values rather than locally re-derived approximations.
        contact_url = "https://baseballsavant.mlb.com/leaderboard/statcast"
        try:
            contact = self._savant_csv(
                contact_url,
                {
                    "type": "batter",
                    "year": season,
                    "position": "",
                    "team": "",
                    "min": 1,
                    "csv": "true",
                },
                fallback=lambda: pb.statcast_batter_exitvelo_barrels(season, minBBE=1),
            )
            row = self._find_player(contact, player_id)
            if row is not None:
                raw = row_to_dict(row)
                overrides = {
                    "Average Exit Velocity": first_existing(raw, ("avg_hit_speed", "avg_exit_velocity")),
                    "Max Exit Velocity": first_existing(raw, ("max_hit_speed", "max_exit_velocity")),
                    "Hard Hit %": self._percent_points(first_existing(raw, ("ev95percent", "hard_hit_percent", "hardhit_percent"))),
                    "Barrel %": self._percent_points(first_existing(raw, ("brl_percent", "barrel_percent", "barrel_pct"))),
                    "Sweet Spot %": self._percent_points(first_existing(raw, ("anglesweetspotpercent", "sweet_spot_percent"))),
                }
                result.update({key: value for key, value in overrides.items() if value is not None})
                sources.append({
                    "name": "Baseball Savant Exit Velocity & Barrels",
                    "url": contact_url,
                    "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
                })
        except Exception as exc:
            LOGGER.warning("Savant contact leaderboard unavailable: %s", exc)

        # Expected statistics use Savant's season leaderboard because xBA/xSLG/
        # xwOBA incorporate strikeouts/walks/HBP and cannot be reproduced by a
        # simple average of batted-ball expected values.
        expected_url = "https://baseballsavant.mlb.com/leaderboard/expected_statistics"
        try:
            expected = self._savant_csv(
                expected_url,
                {
                    "type": "batter",
                    "year": season,
                    "position": "",
                    "team": "",
                    "filterType": "pa",
                    "min": 1,
                    "csv": "true",
                },
                fallback=lambda: pb.statcast_batter_expected_stats(season, minPA=1),
            )
            row = self._find_player(expected, player_id)
            if row is not None:
                raw = row_to_dict(row)
                overrides = {
                    "xBA": first_existing(raw, ("est_ba", "xba", "x_ba")),
                    "xSLG": first_existing(raw, ("est_slg", "xslg", "x_slg")),
                    "xwOBA": first_existing(raw, ("est_woba", "xwoba", "x_woba")),
                }
                result.update({key: value for key, value in overrides.items() if value is not None})
                sources.append({
                    "name": "Baseball Savant Expected Statistics",
                    "url": expected_url,
                    "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
                })
        except Exception as exc:
            LOGGER.warning("Savant expected-stat leaderboard unavailable: %s", exc)

        if frame is not None and not frame.empty:
            sources.append({
                "name": "Baseball Savant Statcast Search (pitch level)",
                "url": "https://baseballsavant.mlb.com/statcast_search",
                "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
            })
        if sources:
            result["_sources"] = sources
        if result:
            self.db.set_player_stats(player_id, "statcast_batter_v5", season, "batter", result)
        return result

    def _aggregate_batter(self, frame: pd.DataFrame) -> dict[str, Any]:
        if frame is None or frame.empty:
            return {}
        result: dict[str, Any] = {}
        launch_speed = pd.to_numeric(frame.get("launch_speed"), errors="coerce")
        launch_angle = pd.to_numeric(frame.get("launch_angle"), errors="coerce")
        bbe_mask = launch_speed.notna()
        bbe = launch_speed[bbe_mask]
        if not bbe.empty:
            result["Average Exit Velocity"] = float(bbe.mean())
            result["Max Exit Velocity"] = float(bbe.max())
            result["Hard Hit %"] = float((bbe >= 95.0).mean() * 100)
            # pybaseball/Statcast CSVs do not consistently expose a dedicated
            # ``barrel`` field. Savant documents launch_speed_angle == 6 as a
            # Barrel, so use that canonical field first and support ``barrel``
            # only as a compatibility fallback.
            if "launch_speed_angle" in frame.columns:
                quality = pd.to_numeric(
                    frame.loc[bbe_mask, "launch_speed_angle"], errors="coerce"
                )
                valid = quality.dropna()
                if not valid.empty:
                    result["Barrel %"] = float((valid == 6).mean() * 100)
            elif "barrel" in frame.columns:
                barrels = pd.to_numeric(
                    frame.loc[bbe_mask, "barrel"], errors="coerce"
                ).dropna()
                if not barrels.empty:
                    result["Barrel %"] = float((barrels == 1).mean() * 100)
            sweet = launch_angle[bbe_mask].between(8, 32, inclusive="both")
            result["Sweet Spot %"] = float(sweet.mean() * 100)
            result["Exit Velocities"] = [float(v) for v in bbe.dropna().tolist()]

        for out_name, column in (
            ("xBA", "estimated_ba_using_speedangle"),
            ("xSLG", "estimated_slg_using_speedangle"),
            ("xwOBA", "estimated_woba_using_speedangle"),
        ):
            if column in frame.columns:
                values = pd.to_numeric(frame[column], errors="coerce").dropna()
                if not values.empty:
                    result[out_name] = float(values.mean())

        swing, whiff, chase = self._swing_metrics(frame)
        result["Whiff %"] = whiff
        result["Chase %"] = chase
        result["Swings"] = swing
        return result

    def get_pitcher_metrics(self, player_id: int, season: int) -> dict[str, Any]:
        cached = self.db.get_player_stats(
            player_id, "statcast_pitcher_v5", season, "pitcher", source_ttl_days(season, savant=True)
        )
        if cached is not None:
            return cached

        pb = self._pybaseball()
        start, end = self.season_dates(season)
        frame = pb.statcast_pitcher(start, end, int(player_id))
        result = self._aggregate_pitcher(frame)

        # Savant season expected-stats leaderboard is the canonical xERA/xBA/xSLG source.
        try:
            expected = self._savant_csv(
                "https://baseballsavant.mlb.com/leaderboard/expected_statistics",
                {"type": "pitcher", "year": season, "position": "", "team": "", "filterType": "pa", "min": 1, "csv": "true"},
                fallback=lambda: pb.statcast_pitcher_expected_stats(season, minPA=1),
            )
            row = self._find_expected_row(expected, player_id)
            if row is not None:
                raw = row_to_dict(row)
                result.update(
                    {
                        "xERA": first_existing(raw, ("xera", "xERA", "est_era")),
                        "xBA": first_existing(raw, ("xba", "xBA", "est_ba")),
                        "xSLG": first_existing(raw, ("xslg", "xSLG", "est_slg")),
                        "xwOBA": first_existing(raw, ("xwoba", "xwOBA", "est_woba")),
                    }
                )
        except Exception as exc:
            LOGGER.warning("Expected-stats leaderboard unavailable: %s", exc)

        if result:
            result["_source"] = {
                "name": "Baseball Savant Statcast pitch-level data",
                "url": "https://baseballsavant.mlb.com/statcast_search",
                "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
            }
            self.db.set_player_stats(player_id, "statcast_pitcher_v5", season, "pitcher", result)
        return result

    def _aggregate_pitcher(self, frame: pd.DataFrame) -> dict[str, Any]:
        if frame is None or frame.empty:
            return {}
        swings, whiff, chase = self._swing_metrics(frame)
        launch_speed = pd.to_numeric(frame.get("launch_speed"), errors="coerce").dropna()
        result: dict[str, Any] = {
            "Whiff %": whiff,
            "Chase %": chase,
            "Swings": swings,
        }
        if not launch_speed.empty:
            result["Average Exit Velocity Allowed"] = float(launch_speed.mean())
        for out_name, column in (
            ("xBA", "estimated_ba_using_speedangle"),
            ("xSLG", "estimated_slg_using_speedangle"),
            ("xwOBA", "estimated_woba_using_speedangle"),
        ):
            if column in frame.columns:
                values = pd.to_numeric(frame[column], errors="coerce").dropna()
                if not values.empty:
                    result[out_name] = float(values.mean())
        return result

    @staticmethod
    def _find_expected_row(frame: pd.DataFrame, player_id: int) -> pd.Series | None:
        if frame is None or frame.empty:
            return None
        for col in ("player_id", "pitcher", "mlbam_id", "id"):
            if col in frame.columns:
                matches = frame[pd.to_numeric(frame[col], errors="coerce") == int(player_id)]
                if not matches.empty:
                    return matches.iloc[0]
        return None

    @staticmethod
    def _swing_metrics(frame: pd.DataFrame) -> tuple[int, float | None, float | None]:
        if "description" not in frame.columns:
            return 0, None, None
        desc = frame["description"].astype(str)
        swing_mask = desc.isin(SWING_DESCRIPTIONS)
        whiff_mask = desc.isin(WHIFF_DESCRIPTIONS)
        swings = int(swing_mask.sum())
        whiff = float(whiff_mask.sum() / swings * 100) if swings else None

        chase = None
        if "zone" in frame.columns:
            zone = pd.to_numeric(frame["zone"], errors="coerce")
            out_zone = zone.notna() & ~zone.between(1, 9, inclusive="both")
            out_zone_pitches = int(out_zone.sum())
            if out_zone_pitches:
                chase = float((swing_mask & out_zone).sum() / out_zone_pitches * 100)
        return swings, whiff, chase

    def get_pitch_arsenal(self, player_id: int, season: int) -> list[dict[str, Any]]:
        cached = self.db.get_pitch_stats(player_id, season, source_ttl_days(season, savant=True))
        if cached is not None:
            return cached
        pb = self._pybaseball()
        start, end = self.season_dates(season)
        frame = pb.statcast_pitcher(start, end, int(player_id))
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
                    # delta_run_exp is from the batting team's perspective; invert it
                    # to display pitcher-positive run prevention.
                    "Run Value": float(-delta.sum()) if delta.notna().any() else None,
                    "Whiff %": self._pitch_whiff_percent(group),
                }
            )
        rows.sort(key=lambda row: float(row.get("Usage %") or 0), reverse=True)
        self.db.set_pitch_stats(player_id, season, rows)
        return rows



    def get_velocity_history(self, player_id: int, season: int) -> list[dict[str, Any]]:
        """Return a monthly primary-fastball velocity trend from Statcast.

        This intentionally does not depend on FanGraphs history: a FanGraphs
        outage must not blank the Velocity tab. The most-used fastball-family
        pitch (FF/SI/FC) is selected, with all pitches as a last-resort fallback.
        """
        cached = self.db.get_player_stats(
            player_id, "statcast_velocity_v3", season, "velocity_history", source_ttl_days(season, savant=True)
        )
        if cached and isinstance(cached.get("rows"), list) and cached["rows"]:
            return cached["rows"]

        pb = self._pybaseball()
        start, end = self.season_dates(season)
        frame = pb.statcast_pitcher(start, end, int(player_id))
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

        work["month"] = work["game_date"].dt.to_period("M").astype(str)
        grouped = work.groupby("month", sort=True)["release_speed"].agg(["mean", "count"])
        rows = [
            {
                "Period": str(month),
                "Avg Velocity": float(row["mean"]),
                "Pitches": int(row["count"]),
                "Pitch": pitch_name,
            }
            for month, row in grouped.iterrows()
            if pd.notna(row["mean"])
        ]
        if rows:
            self.db.set_player_stats(
                player_id, "statcast_velocity_v3", season, "velocity_history", {"rows": rows}
            )
        return rows

    @staticmethod
    def _pitch_whiff_percent(group: pd.DataFrame) -> float | None:
        if "description" not in group.columns:
            return None
        desc = group["description"].astype(str)
        swings = desc.isin(SWING_DESCRIPTIONS)
        count = int(swings.sum())
        if not count:
            return None
        whiffs = desc.isin(WHIFF_DESCRIPTIONS)
        return float(whiffs.sum() / count * 100)

    @staticmethod
    def _normalize_leaderboard_columns(frame: pd.DataFrame) -> pd.DataFrame:
        """Normalize Savant CSV headers without changing the underlying values."""
        if frame is None or frame.empty:
            return frame
        normalized = frame.copy()
        normalized.columns = [
            str(col).strip().lower().replace(" ", "_").replace("%", "pct")
            for col in normalized.columns
        ]
        return normalized

    def _savant_csv(
        self, url: str, params: dict[str, Any], *, fallback: Any | None = None
    ) -> pd.DataFrame:
        """Fetch an official Savant CSV directly, bypassing pybaseball's cache."""
        try:
            text = sync_get_text(url, params=params)
            frame = pd.read_csv(StringIO(text))
            return self._normalize_leaderboard_columns(frame)
        except Exception as exc:
            LOGGER.warning("Direct Baseball Savant CSV failed: %s", exc)
            if fallback is None:
                raise
            frame = fallback()
            return self._normalize_leaderboard_columns(frame)

    def get_defense(self, player_id: int, season: int, position: str) -> dict[str, Any]:
        """Return current Baseball Savant defensive metrics for a fielder.

        OAA is read from the *all positions* Fielder leaderboard and only from
        the actual OAA column. Runs Prevented is a different metric and must
        never be substituted for OAA. Current-season Savant defense uses a
        one-hour cache; historical seasons retain the normal long cache.
        """
        ttl_days = source_ttl_days(season, savant=True)
        cached = self.db.get_player_stats(
            player_id, "statcast_defense_v6", season, "defense", ttl_days
        )
        if cached:
            return cached

        result: dict[str, Any] = {}
        sources: list[dict[str, str]] = []
        # Official Baseball Savant OAA leaderboard. Always request ALL positions
        # so multi-position players match the number shown on the main leaderboard.
        oaa_url = "https://baseballsavant.mlb.com/leaderboard/outs_above_average"
        oaa_params: dict[str, Any] = {
            "type": "Fielder",
            "startYear": season,
            "endYear": season,
            "split": "no",
            "team": "",
            "range": "year",
            "min": 1,
            # Savant uses an empty position query value for the UI's “All”.
            # pybaseball normalizes ALL to the same endpoint representation.
            "pos": "",
            "roles": "",
            "viz": "hide",
            "csv": "true",
        }
        defense_errors: list[str] = []
        if position.upper() != "C":
            try:
                # For the active season, never fall back to pybaseball's cached
                # OAA response. A stale number is worse than a visible source
                # failure. Historical seasons may safely use the wrapper fallback.
                fallback = None
                if season != date.today().year:
                    fallback = lambda: self._pybaseball().statcast_outs_above_average(
                        season, "ALL", min_att=1, view="Fielder"
                    )
                frame = self._savant_csv(oaa_url, oaa_params, fallback=fallback)
                row = self._find_player(frame, player_id)
                if row is None:
                    defense_errors.append(
                        "Baseball Savant OAA: no matching MLBAM player row"
                    )
                else:
                    raw = row_to_dict(row)
                    # Strict mapping: OAA must come only from the leaderboard's
                    # OAA field. Runs Prevented is related, but not interchangeable.
                    oaa_value = first_existing(
                        raw,
                        (
                            "outs_above_average",
                            "n_outs_above_average",
                            "oaa",
                        ),
                    )
                    if oaa_value is None:
                        defense_errors.append(
                            "Baseball Savant OAA: response did not contain an OAA column"
                        )
                    else:
                        try:
                            result["OAA"] = float(oaa_value)
                        except (TypeError, ValueError):
                            result["OAA"] = oaa_value
                    runs_prevented = first_existing(
                        raw, ("fielding_runs_prevented", "runs_prevented")
                    )
                    if runs_prevented is not None:
                        try:
                            result["Runs Prevented"] = float(runs_prevented)
                        except (TypeError, ValueError):
                            result["Runs Prevented"] = runs_prevented

                    exact_url = f"{oaa_url}?{urlencode(oaa_params)}"
                    sources.append(
                        {
                            "name": "Baseball Savant OAA — Fielder / All Positions",
                            "url": exact_url,
                            "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
                        }
                    )
            except Exception as exc:
                LOGGER.warning("OAA unavailable for %s: %s", player_id, exc)
                defense_errors.append(f"Baseball Savant OAA request failed: {exc}")

        # Official Fielding Run Value leaderboard, all positions. This table also
        # exposes the Arm component used by Savant's FRV decomposition.
        frv_url = "https://baseballsavant.mlb.com/leaderboard/fielding-run-value"
        frv_params: dict[str, Any] = {
            "gameType": "Regular",
            "seasonStart": season,
            "seasonEnd": season,
            "type": "fielder",
            "position": 0,
            "minInnings": 0.1,
            "minResults": 1,
            "csv": "true",
        }
        try:
            frame = self._savant_csv(
                frv_url,
                frv_params,
                fallback=lambda: self._pybaseball().statcast_fielding_run_value(
                    season, "ALL", min_inn=1
                ),
            )
            row = self._find_player(frame, player_id)
            if row is not None:
                raw = row_to_dict(row)
                result["Fielding Run Value"] = first_existing(
                    raw,
                    (
                        "fielding_run_value",
                        "total_runs",
                        "fielding_runs",
                        "fielding_run_value_total",
                    ),
                )
                result["Arm Value"] = first_existing(
                    raw,
                    (
                        "arm_runs",
                        "arm",
                        "fielder_throwing_runs",
                        "throwing_runs",
                    ),
                )
                sources.append(
                    {
                        "name": "Baseball Savant Fielding Run Value",
                        "url": f"{frv_url}?{urlencode(frv_params)}",
                        "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
                    }
                )
        except Exception as exc:
            LOGGER.warning("Fielding Run Value unavailable: %s", exc)

        if sources:
            result["_sources"] = sources
        if defense_errors:
            result["_errors"] = defense_errors
        if any(not key.startswith("_") and value is not None for key, value in result.items()):
            self.db.set_player_stats(
                player_id, "statcast_defense_v6", season, "defense", result
            )
        return result

    @staticmethod
    def _find_player(frame: pd.DataFrame, player_id: int) -> pd.Series | None:
        if frame is None or frame.empty:
            return None
        for col in (
            "player_id",
            "playerid",
            "fielder_id",
            "mlbam_id",
            "id",
            "player_id_2",
        ):
            if col in frame.columns:
                matches = frame[pd.to_numeric(frame[col], errors="coerce") == int(player_id)]
                if not matches.empty:
                    return matches.iloc[0]
        return None
