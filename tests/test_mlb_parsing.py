from services.mlb_api import MLBApiService


def test_parse_schedule_game() -> None:
    service = MLBApiService()
    raw = {
        "gamePk": 123,
        "gameDate": "2026-09-10T23:05:00Z",
        "status": {"abstractGameState": "Live", "detailedState": "In Progress"},
        "venue": {"name": "Test Park"},
        "teams": {
            "away": {"score": 4, "team": {"id": 147, "name": "New York Yankees", "abbreviation": "NYY"}},
            "home": {"score": 2, "team": {"id": 111, "name": "Boston Red Sox", "abbreviation": "BOS"}},
        },
        "linescore": {"currentInning": 7, "inningState": "Top"},
    }
    game = service._parse_schedule_game(raw)
    assert game.game_pk == 123
    assert game.matchup == "NYY vs BOS"
    assert game.away.score == 4
    assert game.home.score == 2
    assert game.inning == 7


def test_parse_live_game_and_lineup() -> None:
    service = MLBApiService()
    raw = {
        "gameData": {
            "game": {"pk": 456},
            "status": {"detailedState": "In Progress"},
            "teams": {
                "away": {"id": 1, "name": "Away Club", "abbreviation": "AWY"},
                "home": {"id": 2, "name": "Home Club", "abbreviation": "HME"},
            },
        },
        "liveData": {
            "linescore": {
                "currentInning": 3,
                "inningState": "Bottom",
                "outs": 1,
                "offense": {"first": {"id": 9}, "second": None, "third": None},
                "teams": {"away": {"runs": 1}, "home": {"runs": 2}},
                "innings": [{"num": 1, "away": {"runs": 1}, "home": {"runs": 2}}],
            },
            "boxscore": {
                "teams": {
                    "away": {
                        "battingOrder": [10],
                        "pitchers": [30, 31],
                        "players": {
                            "ID10": {
                                "person": {"fullName": "Away Hitter"},
                                "position": {"abbreviation": "CF"},
                                "battingOrder": "100",
                            },
                            "ID30": {
                                "person": {"fullName": "Away Starter"},
                                "position": {"abbreviation": "P"},
                                "stats": {"pitching": {"inningsPitched": "5.0", "hits": 4, "runs": 2, "earnedRuns": 2, "baseOnBalls": 1, "strikeOuts": 7}},
                            },
                            "ID31": {
                                "person": {"fullName": "Away Reliever"},
                                "position": {"abbreviation": "P"},
                                "stats": {"pitching": {"inningsPitched": "1.0", "hits": 0, "runs": 0, "earnedRuns": 0, "baseOnBalls": 0, "strikeOuts": 2}},
                            },
                        },
                    },
                    "home": {
                        "battingOrder": [],
                        "pitchers": [20],
                        "players": {
                            "ID20": {
                                "person": {"fullName": "Home Starter"},
                                "position": {"abbreviation": "P"},
                                "stats": {"pitching": {"inningsPitched": "5.0", "strikeOuts": 6}},
                            },
                            "ID21": {
                                "person": {"fullName": "Home Reliever"},
                                "position": {"abbreviation": "P"},
                                "stats": {"pitching": {"inningsPitched": "1.0", "strikeOuts": 2}},
                            },
                        },
                    },
                }
            },
            "plays": {
                "currentPlay": {
                    "about": {"inning": 3},
                    "count": {"balls": 2, "strikes": 1, "outs": 1},
                    "matchup": {
                        "batter": {"id": 10, "fullName": "Away Hitter"},
                        "pitcher": {"id": 20, "fullName": "Home Pitcher"},
                    },
                    "result": {"description": "Single to center."},
                },
                "allPlays": [
                    {
                        "about": {"halfInning": "top"},
                        "matchup": {"pitcher": {"id": 20, "fullName": "Home Starter"}},
                        "result": {"description": "Groundout."},
                    },
                    {
                        "about": {"halfInning": "top"},
                        "matchup": {"pitcher": {"id": 21, "fullName": "Home Reliever"}},
                        "result": {"description": "Strikeout."},
                    },
                ],
            },
        },
    }
    detail = service._parse_live_game(raw)
    assert detail.game_pk == 456
    assert detail.balls == 2
    assert detail.strikes == 1
    assert detail.on_first is True
    assert detail.batter and detail.batter.id == 10
    assert detail.pitcher and detail.pitcher.id == 20
    assert detail.away_lineup[0].name == "Away Hitter"
    assert [p.name for p in detail.away_pitchers] == ["Away Starter", "Away Reliever"]
    assert detail.away_pitchers[1].game_stats["strikeOuts"] == 2
    # Play-by-play supplements a partial boxscore pitchers array.
    assert [p.name for p in detail.home_pitchers] == ["Home Starter", "Home Reliever"]
    assert detail.home_pitchers[1].game_stats["strikeOuts"] == 2
