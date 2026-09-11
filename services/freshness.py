from __future__ import annotations

from datetime import date

from config.settings import SETTINGS


def source_ttl_days(season: int, *, savant: bool = False) -> float:
    """Return a shorter TTL for in-progress seasons.

    Historical seasons retain the project's 30-day cache policy. Current-season
    public leaderboards are refreshed much more often so OAA/WAR do not remain
    stale for weeks after the source itself changes.
    """
    if int(season) != date.today().year:
        return float(SETTINGS.cache_ttl_days)
    hours = (
        SETTINGS.current_savant_ttl_hours
        if savant
        else SETTINGS.current_season_cache_ttl_hours
    )
    return float(hours) / 24.0
