from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config.preferences import read_preferences

BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = Path(read_preferences()["data_root"]).expanduser() if read_preferences()["data_root"] else BASE_DIR
CACHE_DIR = RUNTIME_ROOT / "cache"
DATA_DIR = RUNTIME_ROOT / "data"
DB_PATH = DATA_DIR / "mlb_advanced_gameday.sqlite3"
LOG_DIR = RUNTIME_ROOT / "logs"
SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"
QSS_PATH = BASE_DIR / "config" / "dark.qss"
THEME_QSS_PATH = BASE_DIR / "config" / "theme.qss"

@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "Dugout Atlas"
    app_version: str = "1.40"
    refresh_seconds: int = 30
    cache_ttl_days: int = 30
    current_season_cache_ttl_hours: int = 1
    current_savant_ttl_hours: float = 0.25
    request_timeout_seconds: int = 20
    request_retries: int = 3
    user_agent: str = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36 Dugout-Atlas/1.40")
    mlb_api_base: str = "https://statsapi.mlb.com/api"
    mlb_logo_base: str = "https://www.mlbstatic.com/team-logos"

SETTINGS = Settings()

def ensure_runtime_dirs() -> None:
    for path in (CACHE_DIR, DATA_DIR, LOG_DIR): path.mkdir(parents=True, exist_ok=True)
