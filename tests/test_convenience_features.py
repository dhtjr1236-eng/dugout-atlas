from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from services.convenience_features import (
    METRIC_TOOLTIPS,
    game_notification,
    game_snapshot,
)
from services.favorites_service import FavoritesService


def test_favorite_player_roundtrip(tmp_path: Path) -> None:
    store = FavoritesService(tmp_path / "favorites.json")

    assert store.toggle_player(
        123,
        "Test Player",
        "Test Club",
        "CF",
    ) is True
    assert store.is_player(123) is True

    assert store.toggle_player(
        123,
        "Test Player",
        "Test Club",
        "CF",
    ) is False
    assert store.is_player(123) is False


def test_favorite_team_roundtrip(tmp_path: Path) -> None:
    store = FavoritesService(tmp_path / "favorites.json")

    assert store.toggle_team(
        10,
        "Test Team",
        "TST",
    ) is True
    assert store.is_team(10) is True


def test_game_notification_on_score_change() -> None:
    game = SimpleNamespace(
        game_pk=9,
        away=SimpleNamespace(
            id=1,
            name="Away",
            abbreviation="AWY",
            score=2,
        ),
        home=SimpleNamespace(
            id=2,
            name="Home",
            abbreviation="HME",
            score=1,
        ),
        detailed_status="In Progress",
        inning=5,
        inning_state="Top",
    )

    old = (
        1,
        1,
        "In Progress",
        4,
        "Bottom",
    )
    new = game_snapshot(game)

    message = game_notification(old, new, game)

    assert message is not None
    assert "AWY 2 - 1 HME" in message


def test_game_notification_on_status_change() -> None:
    game = SimpleNamespace(
        game_pk=9,
        away=SimpleNamespace(
            id=1,
            name="Away",
            abbreviation="AWY",
            score=2,
        ),
        home=SimpleNamespace(
            id=2,
            name="Home",
            abbreviation="HME",
            score=1,
        ),
        detailed_status="Final",
        inning=9,
        inning_state="End",
    )

    old = (
        2,
        1,
        "In Progress",
        9,
        "Bottom",
    )
    new = game_snapshot(game)

    message = game_notification(old, new, game)

    assert message == "AWY vs HME · Final"


def test_compare_tooltips_cover_core_metrics() -> None:
    for metric in (
        "AVG",
        "OPS",
        "wRC+",
        "fWAR",
        "bWAR",
        "OAA",
        "ERA",
        "FIP",
        "xERA",
    ):
        assert METRIC_TOOLTIPS.get(metric)
