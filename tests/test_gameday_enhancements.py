from __future__ import annotations

from services.gameday_enhancements import extract_scoring_plays


def test_home_run_scoring_play_extracts_rbi_and_scorers() -> None:
    payload = {
        "liveData": {
            "plays": {
                "allPlays": [
                    {
                        "about": {"inning": 3, "halfInning": "top"},
                        "matchup": {"batter": {"id": 10, "fullName": "Slugger"}},
                        "result": {
                            "event": "Home Run",
                            "eventType": "home_run",
                            "description": "Slugger homers. Runner scores.",
                            "rbi": 2,
                            "awayScore": 2,
                            "homeScore": 0,
                        },
                        "runners": [
                            {
                                "movement": {"end": "score"},
                                "details": {
                                    "runner": {"id": 20, "fullName": "Runner"},
                                    "isScoringEvent": True,
                                    "rbi": True,
                                },
                            },
                            {
                                "movement": {"end": "score"},
                                "details": {
                                    "runner": {"id": 10, "fullName": "Slugger"},
                                    "isScoringEvent": True,
                                    "rbi": True,
                                },
                            },
                        ],
                    }
                ]
            }
        }
    }

    rows = extract_scoring_plays(payload)
    assert len(rows) == 1
    assert rows[0]["inning"] == "3회초"
    assert rows[0]["batter"] == "Slugger"
    assert rows[0]["event"] == "HR"
    assert rows[0]["rbi"] == 2
    assert rows[0]["scorers"] == ["Runner", "Slugger"]


def test_non_rbi_run_is_kept_when_score_changes() -> None:
    payload = {
        "liveData": {
            "plays": {
                "allPlays": [
                    {
                        "about": {"inning": 5, "halfInning": "bottom"},
                        "matchup": {"batter": {"fullName": "Current Batter"}},
                        "result": {
                            "event": "Wild Pitch",
                            "eventType": "wild_pitch",
                            "description": "Runner scores on a wild pitch.",
                            "rbi": 0,
                            "awayScore": 0,
                            "homeScore": 1,
                        },
                        "runners": [
                            {
                                "movement": {"end": "score"},
                                "details": {
                                    "runner": {"fullName": "Fast Runner"},
                                    "isScoringEvent": True,
                                    "rbi": False,
                                },
                            }
                        ],
                    }
                ]
            }
        }
    }

    rows = extract_scoring_plays(payload)
    assert len(rows) == 1
    assert rows[0]["event"] == "WP"
    assert rows[0]["rbi"] == 0
    assert rows[0]["scorers"] == ["Fast Runner"]
