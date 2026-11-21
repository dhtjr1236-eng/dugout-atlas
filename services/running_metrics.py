from __future__ import annotations

from config.i18n import tr

import asyncio
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from services.dataframe_utils import row_to_dict
from services.fangraphs_service import FanGraphsService
from services.freshness import source_ttl_days
from services.statcast_service import StatcastService

SPRINT_SPEED_URL = "https://baseballsavant.mlb.com/leaderboard/sprint_speed"
RUNNING_CACHE_SOURCE = "running_metrics_v1"


def _canonical(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def _first_canonical(raw: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    wanted = {_canonical(alias) for alias in aliases}
    for key, value in raw.items():
        if _canonical(key) in wanted and value is not None:
            return value
    return None


def _append_source(container: dict[str, Any], source: dict[str, str]) -> None:
    sources = container.setdefault("_sources", [])
    if not isinstance(sources, list):
        sources = []
        container["_sources"] = sources
    if not any(isinstance(item, dict) and item.get("url") == source.get("url") for item in sources):
        sources.append(source)


def get_sprint_speed(
    service: StatcastService,
    player_id: int,
    season: int,
) -> dict[str, Any]:
    """Return official Baseball Savant seasonal Sprint Speed.

    Sprint Speed is displayed with the official feet-per-second unit. The value is
    read from the Savant Sprint Speed leaderboard, not estimated from pitch or
    batted-ball data.
    """
    cached = service.db.get_player_stats(
        player_id,
        RUNNING_CACHE_SOURCE,
        season,
        "sprint_speed",
        source_ttl_days(season, savant=True),
    )
    if cached:
        return cached

    params: dict[str, Any] = {
        "min_season": season,
        "max_season": season,
        "position": "",
        "team": "",
        "min": 1,
        "csv": "true",
    }
    frame = service._savant_csv(SPRINT_SPEED_URL, params, fallback=None)
    row = service._find_player(frame, player_id)
    if row is None:
        return {}

    raw = row_to_dict(row)
    value = _first_canonical(
        raw,
        (
            "sprint_speed",
            "sprint speed",
            "sprint_speed_ft_sec",
            "sprint speed (ft / sec)",
            "sprint_speed_(ft_/_sec)",
        ),
    )
    if value is None:
        # Savant has changed display headers before; accept any column whose
        # canonical name contains sprintspeed while still requiring a numeric value.
        for key, candidate in raw.items():
            if "sprintspeed" in _canonical(key) and candidate is not None:
                value = candidate
                break
    try:
        speed = float(value)
    except (TypeError, ValueError):
        return {}

    exact_url = f"{SPRINT_SPEED_URL}?{urlencode(params)}"
    result = {
        "Sprint Speed": f"{speed:.1f} ft/s",
        "Sprint Speed Value": speed,
        "_source": {
            "name": "Baseball Savant Sprint Speed Leaderboard",
            "url": exact_url,
            "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
        },
    }
    service.db.set_player_stats(
        player_id,
        RUNNING_CACHE_SOURCE,
        season,
        "sprint_speed",
        result,
    )
    return result


def get_baserunning(
    service: FanGraphsService,
    player_id: int,
    full_name: str,
    season: int,
) -> dict[str, Any]:
    """Return FanGraphs stolen-base results and calculated success rate."""
    cached = service.db.get_player_stats(
        player_id,
        RUNNING_CACHE_SOURCE,
        season,
        "baserunning",
        service._cache_ttl_days(season),
    )
    if cached:
        return cached

    frame = service._season_frame(season, False)
    row = service._find_player_row(frame, player_id, full_name)
    if row is None:
        return {}
    raw = row_to_dict(row)

    def integer_metric(*aliases: str) -> int | None:
        value = _first_canonical(raw, aliases)
        try:
            return int(float(value)) if value is not None else None
        except (TypeError, ValueError):
            return None

    sb = integer_metric("SB", "stolen bases", "stolen_bases")
    cs = integer_metric("CS", "caught stealing", "caught_stealing")
    attempts = (sb or 0) + (cs or 0) if sb is not None or cs is not None else 0
    success = float((sb or 0) / attempts * 100.0) if attempts else None

    result: dict[str, Any] = {
        "SB": sb,
        "CS": cs,
        "SB Success %": success,
        "_source": {
            "name": "FanGraphs Major League Leaderboards — Baserunning",
            "url": service._leaderboard_url(season, season, False),
            "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
        },
    }
    if sb is not None or cs is not None:
        service.db.set_player_stats(
            player_id,
            RUNNING_CACHE_SOURCE,
            season,
            "baserunning",
            result,
        )
    return result


def running_metrics(bundle: Any) -> list[tuple[str, Any, bool]]:
    return [
        ("Sprint Speed", bundle.statcast.get("Sprint Speed"), False),
        ("SB", bundle.fangraphs.get("SB"), False),
        ("CS", bundle.fangraphs.get("CS"), False),
        ("SB Success %", bundle.fangraphs.get("SB Success %"), True),
    ]


def install_running_support() -> None:
    """Install Dugout Atlas 1.11 Running metrics into the existing player page."""
    from PyQt6.QtWidgets import QGroupBox, QVBoxLayout

    from services.player_service import PlayerService
    from ui.player_view import PlayerView
    from ui.widgets.metric_grid import MetricGrid

    if getattr(PlayerService, "_running_patch_installed", False):
        return

    original_get_bundle = PlayerService.get_bundle
    original_init = PlayerView.__init__
    original_show_batter = PlayerView._show_batter
    original_show_pitcher = PlayerView._show_pitcher

    async def get_bundle_with_running(
        self: PlayerService, player_id: int, season: int
    ):
        bundle = await original_get_bundle(self, player_id, season)
        if bundle.profile.is_pitcher:
            return bundle

        sprint_task = asyncio.to_thread(
            get_sprint_speed, self.statcast, player_id, season
        )
        bases_task = asyncio.to_thread(
            get_baserunning,
            self.fangraphs,
            player_id,
            bundle.profile.full_name,
            season,
        )
        sprint_result, bases_result = await asyncio.gather(
            sprint_task, bases_task, return_exceptions=True
        )

        if isinstance(sprint_result, Exception):
            bundle.errors.append(f"Sprint Speed: {sprint_result}")
        elif isinstance(sprint_result, dict):
            for key in ("Sprint Speed", "Sprint Speed Value"):
                if sprint_result.get(key) is not None:
                    bundle.statcast[key] = sprint_result[key]
            source = sprint_result.get("_source")
            if isinstance(source, dict):
                _append_source(bundle.statcast, source)

        if isinstance(bases_result, Exception):
            bundle.errors.append(f"FanGraphs baserunning: {bases_result}")
        elif isinstance(bases_result, dict):
            for key in ("SB", "CS", "SB Success %"):
                if bases_result.get(key) is not None:
                    bundle.fangraphs[key] = bases_result[key]
            source = bases_result.get("_source")
            if isinstance(source, dict):
                _append_source(bundle.fangraphs, source)
        return bundle

    def init_with_running(self: PlayerView) -> None:
        original_init(self)
        self.running_box = QGroupBox(tr("Running"))
        running_layout = QVBoxLayout(self.running_box)
        self.running_grid = MetricGrid(columns=4)
        running_layout.addWidget(self.running_grid)
        defense_index = self.layout.indexOf(self.defense_box)
        self.layout.insertWidget(defense_index + 1, self.running_box)
        self.running_box.hide()

    def show_batter_with_running(self: PlayerView, bundle: Any) -> None:
        original_show_batter(self, bundle)
        self.running_box.show()
        self.running_grid.set_metrics(running_metrics(bundle))

    def show_pitcher_without_running(
        self: PlayerView, bundle: Any, period_payload: dict[str, Any] | None = None
    ) -> None:
        self.running_box.hide()
        original_show_pitcher(self, bundle, period_payload)

    PlayerService.get_bundle = get_bundle_with_running  # type: ignore[method-assign]
    PlayerView.__init__ = init_with_running  # type: ignore[method-assign]
    PlayerView._show_batter = show_batter_with_running  # type: ignore[method-assign]
    PlayerView._show_pitcher = show_pitcher_without_running  # type: ignore[method-assign]
    PlayerService._running_patch_installed = True  # type: ignore[attr-defined]
