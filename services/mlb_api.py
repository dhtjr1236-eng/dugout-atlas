from __future__ import annotations

import asyncio
import logging
from datetime import date
from pathlib import Path
from typing import Any

from cache.file_cache import FileCache
from config.settings import SETTINGS
from models.game import GameDetail, GameSummary, LineupPlayer, TeamRef
from models.player import PlayerProfile
from services.base_http import async_get_bytes, async_get_json

LOGGER = logging.getLogger(__name__)


class MLBApiService:
    """Live MLB Stats API adapter.

    Schedule and game-feed reads are intentionally never served from a cache.
    """

    def __init__(self) -> None:
        self.base = SETTINGS.mlb_api_base.rstrip("/")
        self.file_cache = FileCache()

    async def get_schedule(self, game_date: date | str) -> list[GameSummary]:
        date_text = game_date.isoformat() if isinstance(game_date, date) else str(game_date)
        payload = await async_get_json(
            f"{self.base}/v1/schedule",
            params={
                "sportId": 1,
                "date": date_text,
                "hydrate": "team,linescore,probablePitcher,decisions",
            },
        )
        games: list[GameSummary] = []
        for day in payload.get("dates", []):
            for game in day.get("games", []):
                games.append(self._parse_schedule_game(game))
        return games

    def _parse_schedule_game(self, game: dict[str, Any]) -> GameSummary:
        teams = game.get("teams", {})
        away_data = teams.get("away", {})
        home_data = teams.get("home", {})
        away_team = away_data.get("team", {})
        home_team = home_data.get("team", {})
        linescore = game.get("linescore", {}) or {}
        status = game.get("status", {}) or {}
        venue = game.get("venue", {}) or {}
        return GameSummary(
            game_pk=int(game.get("gamePk", 0)),
            game_date=str(game.get("gameDate", "")),
            status=str(status.get("abstractGameState", "Unknown")),
            detailed_status=str(status.get("detailedState", "Unknown")),
            away=TeamRef(
                id=int(away_team.get("id", 0)),
                name=str(away_team.get("name", "Away")),
                abbreviation=str(away_team.get("abbreviation", "")),
                score=self._safe_int(away_data.get("score")),
            ),
            home=TeamRef(
                id=int(home_team.get("id", 0)),
                name=str(home_team.get("name", "Home")),
                abbreviation=str(home_team.get("abbreviation", "")),
                score=self._safe_int(home_data.get("score")),
            ),
            inning=self._safe_int(linescore.get("currentInning")),
            inning_state=str(linescore.get("inningState", "")),
            venue=str(venue.get("name", "")),
        )

    async def get_live_game(self, game_pk: int) -> GameDetail:
        payload = await async_get_json(
            f"{self.base}/v1.1/game/{game_pk}/feed/live"
        )
        return self._parse_live_game(payload)

    def _parse_live_game(self, payload: dict[str, Any]) -> GameDetail:
        game_data = payload.get("gameData", {}) or {}
        live_data = payload.get("liveData", {}) or {}
        teams = game_data.get("teams", {}) or {}
        linescore = live_data.get("linescore", {}) or {}
        boxscore = live_data.get("boxscore", {}) or {}
        plays = live_data.get("plays", {}) or {}
        current_play = plays.get("currentPlay", {}) or {}
        about = current_play.get("about", {}) or {}
        matchup = current_play.get("matchup", {}) or {}
        count = current_play.get("count", {}) or {}

        away_box = (boxscore.get("teams", {}) or {}).get("away", {}) or {}
        home_box = (boxscore.get("teams", {}) or {}).get("home", {}) or {}

        away_team_data = teams.get("away", {}) or {}
        home_team_data = teams.get("home", {}) or {}
        away_line = ((linescore.get("teams", {}) or {}).get("away", {}) or {})
        home_line = ((linescore.get("teams", {}) or {}).get("home", {}) or {})
        away_score = away_line.get("runs")
        home_score = home_line.get("runs")

        offense = linescore.get("offense", {}) or {}
        status = game_data.get("status", {}) or {}

        recent_play = ""
        result = current_play.get("result", {}) or {}
        if result:
            recent_play = str(result.get("description", ""))
        if not recent_play:
            all_plays = plays.get("allPlays", []) or []
            if all_plays:
                recent_result = (all_plays[-1].get("result", {}) or {})
                recent_play = str(recent_result.get("description", ""))

        away = TeamRef(
            id=int(away_team_data.get("id", 0)),
            name=str(away_team_data.get("name", "Away")),
            abbreviation=str(away_team_data.get("abbreviation", "")),
            score=self._safe_int(away_score),
        )
        home = TeamRef(
            id=int(home_team_data.get("id", 0)),
            name=str(home_team_data.get("name", "Home")),
            abbreviation=str(home_team_data.get("abbreviation", "")),
            score=self._safe_int(home_score),
        )

        innings: list[dict[str, Any]] = []
        for inning in linescore.get("innings", []) or []:
            innings.append(
                {
                    "num": inning.get("num"),
                    "away": (inning.get("away", {}) or {}).get("runs"),
                    "home": (inning.get("home", {}) or {}).get("runs"),
                }
            )

        return GameDetail(
            game_pk=int(game_data.get("game", {}).get("pk") or payload.get("gamePk") or 0),
            away=away,
            home=home,
            status=str(status.get("detailedState", "Unknown")),
            balls=int(count.get("balls") or 0),
            strikes=int(count.get("strikes") or 0),
            outs=int(count.get("outs") or linescore.get("outs") or 0),
            inning=self._safe_int(about.get("inning") or linescore.get("currentInning")),
            inning_state=str(linescore.get("inningState", "")),
            on_first=bool(offense.get("first")),
            on_second=bool(offense.get("second")),
            on_third=bool(offense.get("third")),
            batter=self._person_from_matchup(matchup.get("batter")),
            pitcher=self._person_from_matchup(matchup.get("pitcher")),
            recent_play=recent_play,
            away_lineup=self._extract_lineup(away_box),
            home_lineup=self._extract_lineup(home_box),
            away_pitchers=self._extract_pitchers(
                away_box, self._pitchers_from_plays(plays, team_side="away")
            ),
            home_pitchers=self._extract_pitchers(
                home_box, self._pitchers_from_plays(plays, team_side="home")
            ),
            away_hits=self._safe_int(away_line.get("hits")),
            home_hits=self._safe_int(home_line.get("hits")),
            away_errors=self._safe_int(away_line.get("errors")),
            home_errors=self._safe_int(home_line.get("errors")),
            linescore=innings,
            raw=payload,
        )

    @staticmethod
    def _person_from_matchup(data: Any) -> LineupPlayer | None:
        if not isinstance(data, dict) or not data.get("id"):
            return None
        return LineupPlayer(id=int(data["id"]), name=str(data.get("fullName", "")))

    def _extract_lineup(self, team_box: dict[str, Any]) -> list[LineupPlayer]:
        players = team_box.get("players", {}) or {}
        order = team_box.get("battingOrder", []) or []
        result: list[LineupPlayer] = []
        for raw_id in order:
            player_id = int(raw_id)
            pdata = players.get(f"ID{player_id}", {}) or {}
            person = pdata.get("person", {}) or {}
            position = pdata.get("position", {}) or {}
            batting_order_raw = pdata.get("battingOrder")
            batting_order = None
            try:
                batting_order = int(str(batting_order_raw)) // 100
            except (TypeError, ValueError):
                pass
            result.append(
                LineupPlayer(
                    id=player_id,
                    name=str(person.get("fullName", f"Player {player_id}")),
                    position=str(position.get("abbreviation", "")),
                    batting_order=batting_order,
                )
            )

        # Add current pitcher if not already listed, useful before a lineup is posted.
        pitcher_id = team_box.get("teamStats", {}).get("pitching")
        _ = pitcher_id  # teamStats has no player identity; kept for schema compatibility.
        return result

    @staticmethod
    def _pitchers_from_plays(
        plays: dict[str, Any], *, team_side: str
    ) -> list[tuple[int, str]]:
        """Collect actual pitcher appearances from play-by-play in first-use order.

        Away pitchers work the bottom half; home pitchers work the top half.
        This supplements the boxscore ``pitchers`` array so completed/live feeds
        cannot silently collapse to only the starter when that array is partial.
        """
        wanted_half = "bottom" if team_side == "away" else "top"
        result: list[tuple[int, str]] = []
        seen: set[int] = set()
        for play in plays.get("allPlays", []) or []:
            if not isinstance(play, dict):
                continue
            about = play.get("about", {}) or {}
            half = str(about.get("halfInning", "")).lower()
            if half != wanted_half:
                continue
            matchup = play.get("matchup", {}) or {}
            pitcher = matchup.get("pitcher", {}) or {}
            try:
                pitcher_id = int(pitcher.get("id"))
            except (TypeError, ValueError):
                continue
            if pitcher_id in seen:
                continue
            seen.add(pitcher_id)
            result.append((pitcher_id, str(pitcher.get("fullName", ""))))
        return result

    def _extract_pitchers(
        self,
        team_box: dict[str, Any],
        play_pitchers: list[tuple[int, str]] | None = None,
    ) -> list[LineupPlayer]:
        """Return every pitcher who has appeared, in MLB boxscore order.

        The live boxscore exposes a team-level ``pitchers`` id array and per-player
        pitching lines. During a game this array grows as relievers enter.
        """
        players = team_box.get("players", {}) or {}
        pitcher_ids = list(team_box.get("pitchers", []) or [])
        appearance_names = {pid: name for pid, name in (play_pitchers or [])}
        for pitcher_id, _name in play_pitchers or []:
            if pitcher_id not in pitcher_ids:
                pitcher_ids.append(pitcher_id)

        result: list[LineupPlayer] = []
        seen: set[int] = set()

        for raw_id in pitcher_ids:
            try:
                player_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if player_id in seen:
                continue
            seen.add(player_id)
            pdata = players.get(f"ID{player_id}", {}) or {}
            person = pdata.get("person", {}) or {}
            position = pdata.get("position", {}) or {}
            stats_root = pdata.get("stats", {}) or {}
            pitching = stats_root.get("pitching", {}) or {}
            if not pitching:
                pitching = ((pdata.get("gameStats", {}) or {}).get("pitching", {}) or {})
            result.append(
                LineupPlayer(
                    id=player_id,
                    name=str(
                        person.get("fullName")
                        or appearance_names.get(player_id)
                        or f"Player {player_id}"
                    ),
                    position=str(position.get("abbreviation", "P")) or "P",
                    game_stats=dict(pitching),
                )
            )

        # Defensive fallback for feeds where the array is absent but player
        # pitching lines are already present. Preserve player-map order.
        if not result:
            for key, pdata in players.items():
                if not isinstance(pdata, dict):
                    continue
                stats_root = pdata.get("stats", {}) or {}
                pitching = stats_root.get("pitching", {}) or {}
                if not pitching:
                    pitching = ((pdata.get("gameStats", {}) or {}).get("pitching", {}) or {})
                batters_faced = pitching.get("battersFaced")
                innings = pitching.get("inningsPitched")
                if not pitching or (batters_faced in (None, 0, "0") and innings in (None, "", "0.0")):
                    continue
                try:
                    player_id = int(str(key).replace("ID", ""))
                except ValueError:
                    person = pdata.get("person", {}) or {}
                    try:
                        player_id = int(person.get("id"))
                    except (TypeError, ValueError):
                        continue
                person = pdata.get("person", {}) or {}
                position = pdata.get("position", {}) or {}
                result.append(
                    LineupPlayer(
                        id=player_id,
                        name=str(person.get("fullName", f"Player {player_id}")),
                        position=str(position.get("abbreviation", "P")) or "P",
                        game_stats=dict(pitching),
                    )
                )
        return result

    async def get_player_profile(self, player_id: int) -> PlayerProfile:
        payload = await async_get_json(
            f"{self.base}/v1/people/{player_id}",
            params={"hydrate": "currentTeam"},
        )
        people = payload.get("people", []) or []
        if not people:
            raise LookupError(f"MLB player {player_id} not found")
        person = people[0]
        current_team = person.get("currentTeam", {}) or {}
        position = person.get("primaryPosition", {}) or {}
        bat_side = person.get("batSide", {}) or {}
        pitch_hand = person.get("pitchHand", {}) or {}
        return PlayerProfile(
            id=int(person.get("id", player_id)),
            full_name=str(person.get("fullName", "Unknown")),
            team=str(current_team.get("name", "")),
            position=str(position.get("abbreviation", "")),
            age=self._safe_int(person.get("currentAge")),
            bats=str(bat_side.get("description", bat_side.get("code", ""))),
            throws=str(pitch_hand.get("description", pitch_hand.get("code", ""))),
            birth_date=str(person.get("birthDate", "")),
            primary_number=str(person.get("primaryNumber", "")),
        )

    async def get_player_season_stats(
        self, player_id: int, season: int, group: str
    ) -> dict[str, Any]:
        payload = await async_get_json(
            f"{self.base}/v1/people/{player_id}/stats",
            params={"stats": "season", "group": group, "season": season},
        )
        stats = payload.get("stats", []) or []
        for bucket in stats:
            splits = bucket.get("splits", []) or []
            if splits:
                return dict(splits[0].get("stat", {}) or {})
        return {}

    async def search_people(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        text = query.strip()
        if not text:
            return []
        payload = await async_get_json(
            f"{self.base}/v1/people/search",
            params={"names": text, "sportIds": 1, "hydrate": "currentTeam"},
        )
        results: list[dict[str, Any]] = []
        for person in payload.get("people", []) or []:
            results.append(
                {
                    "id": int(person.get("id", 0)),
                    "name": str(person.get("fullName", "")),
                    "position": str((person.get("primaryPosition", {}) or {}).get("abbreviation", "")),
                    "team": str((person.get("currentTeam", {}) or {}).get("name", "")),
                }
            )
            if len(results) >= limit:
                break
        return results

    async def get_team_logo(self, team_id: int) -> Path | None:
        path = self.file_cache.path_for("team_logos", f"{team_id}.svg")
        if self.file_cache.is_fresh(path, SETTINGS.cache_ttl_days):
            return path
        try:
            data = await async_get_bytes(f"{SETTINGS.mlb_logo_base}/{team_id}.svg")
            path.write_bytes(data)
            return path
        except Exception as exc:  # Logo failure should never break a game screen.
            LOGGER.warning("Could not download logo for team %s: %s", team_id, exc)
            return path if path.exists() else None

    async def get_team_logos(self, team_ids: list[int]) -> dict[int, Path | None]:
        unique_ids = sorted({team_id for team_id in team_ids if team_id})
        paths = await asyncio.gather(
            *(self.get_team_logo(team_id) for team_id in unique_ids),
            return_exceptions=True,
        )
        result: dict[int, Path | None] = {}
        for team_id, path in zip(unique_ids, paths, strict=True):
            result[team_id] = None if isinstance(path, Exception) else path
        return result

    async def get_standings(self, season: int, standings_type: str = "regularSeason") -> list[dict[str, Any]]:
        payload = await async_get_json(
            f"{self.base}/v1/standings",
            params={
                "leagueId": "103,104",
                "season": season,
                "standingsTypes": standings_type,
                "hydrate": "team",
            },
        )
        rows: list[dict[str, Any]] = []
        for record in payload.get("records", []) or []:
            division = record.get("division", {}) or {}
            league = record.get("league", {}) or {}
            for team_record in record.get("teamRecords", []) or []:
                team = team_record.get("team", {}) or {}
                rows.append(
                    {
                        "team_id": int(team.get("id", 0)),
                        "team": str(team.get("name", "")),
                        "wins": int(team_record.get("wins", 0)),
                        "losses": int(team_record.get("losses", 0)),
                        "pct": str(team_record.get("winningPercentage", "")),
                        "games_back": str(team_record.get("gamesBack", "")),
                        "division_rank": str(team_record.get("divisionRank", "")),
                        "league_rank": str(team_record.get("leagueRank", "")),
                        "wild_card_rank": str(team_record.get("wildCardRank", "")),
                        "division": str(division.get("name", "")),
                        "league": str(league.get("name", "")),
                    }
                )
        return rows

    async def get_league_team_stats(self, season: int) -> list[dict[str, Any]]:
        """Return team-level hitting and pitching season stats for MLB."""
        async def fetch(group: str) -> dict[int, dict[str, Any]]:
            payload = await async_get_json(
                f"{self.base}/v1/teams/stats",
                params={
                    "stats": "season",
                    "group": group,
                    "season": season,
                    "sportIds": 1,
                },
            )
            result: dict[int, dict[str, Any]] = {}
            for bucket in payload.get("stats", []) or []:
                for split in bucket.get("splits", []) or []:
                    team = split.get("team", {}) or {}
                    team_id = int(team.get("id", 0))
                    if team_id:
                        result[team_id] = {
                            "team_id": team_id,
                            "team": str(team.get("name", "")),
                            **dict(split.get("stat", {}) or {}),
                        }
            return result

        hitting, pitching = await asyncio.gather(fetch("hitting"), fetch("pitching"))
        team_ids = sorted(set(hitting) | set(pitching))
        rows: list[dict[str, Any]] = []
        for team_id in team_ids:
            hit = hitting.get(team_id, {})
            pit = pitching.get(team_id, {})
            rows.append(
                {
                    "team_id": team_id,
                    "team": hit.get("team") or pit.get("team") or str(team_id),
                    "R": hit.get("runs"),
                    "HR": hit.get("homeRuns"),
                    "AVG": hit.get("avg"),
                    "OBP": hit.get("obp"),
                    "SLG": hit.get("slg"),
                    "OPS": hit.get("ops"),
                    "ERA": pit.get("era"),
                    "WHIP": pit.get("whip"),
                    "SO": pit.get("strikeOuts"),
                }
            )
        return rows

    async def get_team_season_stats(self, team_id: int, season: int) -> dict[str, Any]:
        payload = await async_get_json(
            f"{self.base}/v1/teams/{team_id}/stats",
            params={"stats": "season", "group": "hitting,pitching", "season": season},
        )
        result: dict[str, Any] = {}
        for bucket in payload.get("stats", []) or []:
            group = str((bucket.get("group", {}) or {}).get("displayName", "")).lower()
            splits = bucket.get("splits", []) or []
            if splits:
                result[group] = splits[0].get("stat", {}) or {}
        return result

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
