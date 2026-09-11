PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL,
    team TEXT,
    position TEXT,
    profile_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS player_stats (
    player_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    season INTEGER NOT NULL,
    role TEXT NOT NULL,
    data_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (player_id, source, season, role)
);

CREATE TABLE IF NOT EXISTS pitch_stats (
    player_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    pitch_type TEXT NOT NULL,
    data_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (player_id, season, pitch_type)
);

CREATE TABLE IF NOT EXISTS games (
    game_pk INTEGER PRIMARY KEY,
    game_date TEXT NOT NULL,
    status TEXT NOT NULL,
    data_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS team_cache (
    team_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    abbreviation TEXT,
    logo_path TEXT,
    data_json TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_player_stats_updated_at ON player_stats(updated_at);
CREATE INDEX IF NOT EXISTS idx_pitch_stats_updated_at ON pitch_stats(updated_at);
CREATE INDEX IF NOT EXISTS idx_games_game_date ON games(game_date);
