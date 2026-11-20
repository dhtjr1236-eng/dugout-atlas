from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from database.sqlite_manager import SQLiteManager
from services.bref_service import BaseballReferenceService
from services.bref_local_store import BRefLocalStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test Baseball-Reference source/import status without the app cache."
    )
    parser.add_argument("--player-id", type=int, default=592450, help="MLBAM player id")
    parser.add_argument("--season", type=int, default=2026, help="Season")
    parser.add_argument("--name", default="Aaron Judge", help="Player full name")
    parser.add_argument(
        "--pitcher",
        action="store_true",
        help="Treat the player as a pitcher (default: batter)",
    )
    parser.add_argument(
        "--import-file",
        type=Path,
        default=None,
        help="Optional official B-Ref WAR ZIP/TXT/CSV to import before testing.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent
    schema = root / "database" / "schema.sql"

    # Normal app import store: this makes the diagnostic reflect what the GUI
    # will actually see after an import.
    local_store = BRefLocalStore(root / "data" / "bref")
    if args.import_file is not None:
        imported = local_store.import_path(args.import_file)
        print("\n=== Imported B-Ref snapshot ===")
        print(json.dumps(imported.to_dict(), ensure_ascii=False, indent=2))

    with tempfile.TemporaryDirectory(prefix="mlb_gameday_diag_") as tmp:
        db = SQLiteManager(Path(tmp) / "diag.sqlite3", schema)
        service = BaseballReferenceService(db)
        service.local_store = local_store
        BaseballReferenceService._daily_cache.clear()
        BaseballReferenceService.reset_network_breaker()
        result = service.get_bwar(
            args.player_id,
            args.season,
            args.pitcher,
            args.name,
        )
        snapshot = service.local_snapshot_status()

    print("\n=== Baseball-Reference diagnostic ===")
    print(f"Player: {args.name} (MLBAM {args.player_id})")
    print(f"Season: {args.season}")
    print("Local snapshot:")
    print(json.dumps(snapshot, ensure_ascii=False, indent=2, default=str))
    print("Result:")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    status = result.get("_status")
    if status == "ok":
        print("\nRESULT: OK - Baseball-Reference values were loaded.")
        return 0
    if status == "partial":
        print("\nRESULT: PARTIAL - official B-Ref data loaded, but not every + metric is present.")
        return 2

    print("\nRESULT: UNAVAILABLE")
    print(
        "If HTTP 403 is shown, use a normal browser to open "
        "https://www.baseball-reference.com/data/, download the latest WAR archive, "
        "then import it with the app's 'B-Ref 파일 가져오기' button."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
