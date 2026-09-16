from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from services.dataframe_utils import first_existing, row_to_dict
from services.fangraphs_service import CURRENT_FG_TTL_MINUTES, FG_LEADERS_URL, FanGraphsService

FG_FIELDING_CACHE_SOURCE = "fangraphs_fielding_oaa_v1"


def _fielding_params(season: int) -> dict[str, Any]:
    return {
        "age": "",
        "pos": "all",
        "stats": "fld",
        "lg": "all",
        "qual": "0",
        "season": season,
        "season1": season,
        "startdate": "",
        "enddate": "",
        "month": "0",
        "team": "0",
        "pageitems": "10000",
        "pagenum": "1",
        "ind": "1",
        "rost": "0",
        "players": "",
        "type": "1",
        "postseason": "",
        "sortdir": "default",
        "sortstat": "OAA",
    }


def get_fangraphs_oaa(
    service: FanGraphsService,
    player_id: int,
    full_name: str,
    season: int,
) -> dict[str, Any]:
    """Return FanGraphs' Statcast OAA from the fielding leaderboard.

    This is intentionally kept separate from Baseball Savant's official OAA card so
    the UI can show both values side-by-side with distinct provenance.
    """
    ttl_days = CURRENT_FG_TTL_MINUTES / (24.0 * 60.0)
    cached = service.db.get_player_stats(
        player_id,
        FG_FIELDING_CACHE_SOURCE,
        season,
        "fielding_oaa",
        ttl_days,
    )
    if cached:
        return cached

    params = _fielding_params(season)
    payload = service._request_json(FG_LEADERS_URL, params)
    rows = payload.get("data", [])

    import pandas as pd

    frame = pd.DataFrame(rows if isinstance(rows, list) else [])
    row = service._find_player_row(frame, player_id, full_name)
    if row is None:
        return {}

    raw = row_to_dict(row)
    value = first_existing(
        raw,
        (
            "OAA",
            "oaa",
            "Statcast OAA",
            "statcast_oaa",
            "Outs Above Average",
        ),
    )
    if value is None:
        return {}

    try:
        oaa = float(value)
    except (TypeError, ValueError):
        return {}

    result = {
        "FanGraphs OAA": oaa,
        "_source": {
            "name": "FanGraphs Fielding Leaderboard — Statcast OAA",
            "url": f"{FG_LEADERS_URL}?{urlencode(params)}",
            "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
        },
    }
    service.db.set_player_stats(
        player_id,
        FG_FIELDING_CACHE_SOURCE,
        season,
        "fielding_oaa",
        result,
    )
    return result


def defense_metrics(bundle: Any) -> list[tuple[str, Any, bool]]:
    defense = bundle.defense
    return [
        ("OAA", defense.get("OAA"), False),
        ("FanGraphs OAA", defense.get("FanGraphs OAA"), False),
        ("Runs Prevented", defense.get("Runs Prevented"), False),
        ("Fielding Run Value", defense.get("Fielding Run Value"), False),
        ("Arm Value", defense.get("Arm Value"), False),
    ]


def install_fangraphs_oaa_support() -> None:
    """Install the 1.10.2 FanGraphs OAA integration without disturbing v1.10.1 logic."""
    from services.player_service import PlayerService
    from ui.player_view import PlayerView

    if getattr(PlayerService, "_fangraphs_oaa_patch_installed", False):
        return

    original_get_bundle = PlayerService.get_bundle
    original_show_batter = PlayerView._show_batter

    async def get_bundle_with_fangraphs_oaa(
        self: PlayerService, player_id: int, season: int
    ):
        bundle = await original_get_bundle(self, player_id, season)
        if bundle.profile.is_pitcher:
            return bundle
        try:
            fg_defense = await asyncio.to_thread(
                get_fangraphs_oaa,
                self.fangraphs,
                player_id,
                bundle.profile.full_name,
                season,
            )
            if fg_defense.get("FanGraphs OAA") is not None:
                bundle.defense["FanGraphs OAA"] = fg_defense["FanGraphs OAA"]
                source = fg_defense.get("_source")
                if isinstance(source, dict):
                    sources = bundle.defense.setdefault("_sources", [])
                    if isinstance(sources, list):
                        sources.append(source)
        except Exception as exc:
            bundle.errors.append(f"FanGraphs fielding OAA: {exc}")
        return bundle

    def show_batter_with_fangraphs_oaa(self: PlayerView, bundle: Any) -> None:
        original_show_batter(self, bundle)
        self.defense_grid.set_metrics(defense_metrics(bundle))

    PlayerService.get_bundle = get_bundle_with_fangraphs_oaa  # type: ignore[method-assign]
    PlayerView._show_batter = show_batter_with_fangraphs_oaa  # type: ignore[method-assign]
    PlayerService._fangraphs_oaa_patch_installed = True  # type: ignore[attr-defined]
