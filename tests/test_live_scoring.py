from types import SimpleNamespace

from services.live_scoring import extract_scoring_plays


def test_home_run_scoring_summary() -> None:
    detail = SimpleNamespace(
        raw={
            "liveData": {
                "plays": {
                    "allPlays": [
                        {
                            "about": {"inning": 3, "halfInning": "top", "isScoringPlay": True},
                            "matchup": {"batter": {"fullName": "Test Hitter"}},
                            "result": {
                                "event": "Home Run",
                                "eventType": "home_run",
                                "rbi": 2,
                                "description": "Test Hitter homers to right. Runner scores.",
                            },
                            "runners": [
                                {"movement": {"end": "score"}, "details": {"runner": {"fullName": "Runner One"}}},
                                {"movement": {"end": "score"}, "details": {"runner": {"fullName": "Test Hitter"}}},
                            ],
                        }
                    ]
                }
            }
        }
    )
    rows = extract_scoring_plays(detail)
    assert rows[0]["inning"] == "3회초"
    assert rows[0]["play"] == "HR"
    assert rows[0]["rbi"] == 2
    assert rows[0]["scorers"] == "Runner One, Test Hitter"


def test_non_rbi_run_is_kept_when_runner_scores() -> None:
    detail = SimpleNamespace(
        raw={
            "liveData": {
                "plays": {
                    "allPlays": [
                        {
                            "about": {"inning": 8, "halfInning": "bottom", "isScoringPlay": True},
                            "matchup": {"batter": {"fullName": "Batter"}},
                            "result": {
                                "event": "Wild Pitch",
                                "eventType": "wild_pitch",
                                "rbi": 0,
                                "description": "Runner scores on a wild pitch.",
                            },
                            "runners": [
                                {"movement": {"end": "score"}, "details": {"runner": {"fullName": "Fast Runner"}}}
                            ],
                        }
                    ]
                }
            }
        }
    )
    rows = extract_scoring_plays(detail)
    assert rows[0]["play"] == "WP"
    assert rows[0]["rbi"] == 0
    assert rows[0]["scorers"] == "Fast Runner"
