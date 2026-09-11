from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
import pandas as pd

from config.settings import DATA_DIR

LOGGER = logging.getLogger(__name__)

BREF_DATA_PAGE = "https://www.baseball-reference.com/data/"


@dataclass(slots=True)
class ImportedDataset:
    role: str
    rows: int
    destination: str
    member_name: str


@dataclass(slots=True)
class BRefImportResult:
    source_file: str
    imported_at: str
    datasets: list[ImportedDataset]

    @property
    def batting_rows(self) -> int:
        return sum(item.rows for item in self.datasets if item.role == "batting")

    @property
    def pitching_rows(self) -> int:
        return sum(item.rows for item in self.datasets if item.role == "pitching")

    def to_dict(self) -> dict[str, object]:
        return {
            "source_file": self.source_file,
            "imported_at": self.imported_at,
            "batting_rows": self.batting_rows,
            "pitching_rows": self.pitching_rows,
            "datasets": [asdict(item) for item in self.datasets],
        }


class BRefLocalStore:
    """Local store for user-downloaded official Baseball-Reference WAR files.

    Baseball-Reference may return HTTP 403 to non-browser requests. This class
    intentionally does not try to defeat that restriction. Instead it accepts
    the official daily WAR text/CSV files or a ``war_archive-YYYY-MM-DD.zip``
    downloaded by the user in a browser, validates the contained tables, and
    persists normalized CSV snapshots for the application.
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or (DATA_DIR / "bref"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.meta_path = self.root / "import_meta.json"

    def dataset_path(self, pitcher: bool) -> Path:
        return self.root / ("war_daily_pitch.csv" if pitcher else "war_daily_bat.csv")

    def load(self, pitcher: bool) -> pd.DataFrame:
        path = self.dataset_path(pitcher)
        if not path.exists():
            return pd.DataFrame()
        try:
            frame = pd.read_csv(path, low_memory=False)
        except Exception as exc:
            LOGGER.warning("Failed to read local B-Ref snapshot %s: %s", path, exc)
            return pd.DataFrame()
        if not self._valid_war_frame(frame):
            LOGGER.warning("Ignoring invalid local B-Ref snapshot: %s", path)
            return pd.DataFrame()
        return frame

    def metadata(self) -> dict[str, object]:
        if not self.meta_path.exists():
            return {}
        try:
            payload = json.loads(self.meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def snapshot_info(self, pitcher: bool) -> dict[str, str]:
        meta = self.metadata()
        role = "pitching" if pitcher else "batting"
        path = self.dataset_path(pitcher)
        roles = meta.get("roles") if isinstance(meta.get("roles"), dict) else {}
        role_meta = roles.get(role) if isinstance(roles, dict) else {}
        if not isinstance(role_meta, dict):
            role_meta = {}
        source_file = str(role_meta.get("source_file") or "")
        source_name = Path(source_file).name if source_file else "local file"
        data_date = str(role_meta.get("data_date") or "")
        name = f"Baseball-Reference official WAR snapshot (local import · {source_name})"
        if data_date:
            name += f" · data {data_date}"
        return {
            "name": name,
            "url": BREF_DATA_PAGE,
            "as_of": str(role_meta.get("imported_at") or meta.get("last_imported_at") or ""),
            "local_file": str(path),
            "source_file": source_file,
            "role": role,
            "data_date": data_date,
        }

    def import_path(self, source: Path | str) -> BRefImportResult:
        path = Path(source).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"B-Ref import file not found: {path}")

        candidates: list[tuple[str, bytes]] = []
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    if info.is_dir() or info.file_size <= 0:
                        continue
                    lower = info.filename.casefold()
                    if not (
                        "war" in lower
                        or lower.endswith((".txt", ".csv", ".tsv"))
                    ):
                        continue
                    # WAR daily files are small enough that this protects against
                    # accidental giant ZIP members while remaining generous.
                    if info.file_size > 100 * 1024 * 1024:
                        continue
                    candidates.append((info.filename, archive.read(info)))
        else:
            candidates.append((path.name, path.read_bytes()))

        if not candidates:
            raise ValueError("No readable WAR table was found in the selected file.")

        selected: dict[str, tuple[str, pd.DataFrame]] = {}
        parse_errors: list[str] = []
        for member_name, raw in candidates:
            try:
                frame = self._read_frame(raw)
            except Exception as exc:
                parse_errors.append(f"{member_name}: {exc}")
                continue
            if frame.empty or not self._valid_war_frame(frame):
                continue
            role = self._classify(member_name, frame)
            if role is None:
                continue
            existing = selected.get(role)
            # Prefer the largest valid table if a ZIP contains multiple related
            # CSVs or historical snapshots.
            if existing is None or len(frame) > len(existing[1]):
                selected[role] = (member_name, frame)

        if not selected:
            detail = f" ({'; '.join(parse_errors[:3])})" if parse_errors else ""
            raise ValueError(
                "The selected file does not contain a recognizable Baseball-Reference "
                f"daily WAR table{detail}."
            )

        imported_at = datetime.now(UTC).isoformat(timespec="seconds")
        datasets: list[ImportedDataset] = []
        for role, (member_name, frame) in selected.items():
            pitcher = role == "pitching"
            destination = self.dataset_path(pitcher)
            self._atomic_write_csv(frame, destination)
            datasets.append(
                ImportedDataset(
                    role=role,
                    rows=len(frame),
                    destination=str(destination),
                    member_name=member_name,
                )
            )

        result = BRefImportResult(
            source_file=str(path),
            imported_at=imported_at,
            datasets=sorted(datasets, key=lambda item: item.role),
        )
        previous = self.metadata()
        previous_roles = previous.get("roles") if isinstance(previous.get("roles"), dict) else {}
        roles: dict[str, object] = dict(previous_roles) if isinstance(previous_roles, dict) else {}
        data_date = self._date_from_name(path.name)
        for item in result.datasets:
            roles[item.role] = {
                "source_file": str(path),
                "member_name": item.member_name,
                "imported_at": imported_at,
                "rows": item.rows,
                "destination": item.destination,
                "data_date": data_date or self._date_from_name(item.member_name),
            }
        meta_payload: dict[str, object] = {
            "last_imported_at": imported_at,
            "last_source_file": str(path),
            "roles": roles,
        }
        self._atomic_write_json(meta_payload, self.meta_path)
        return result

    @staticmethod
    def _read_frame(raw: bytes) -> pd.DataFrame:
        # B-Ref WAR files are comma-delimited text. ``utf-8-sig`` gracefully
        # handles either plain UTF-8 or a BOM.
        text = raw.decode("utf-8-sig", errors="replace")
        frame = pd.read_csv(BytesIO(text.encode("utf-8")), low_memory=False)
        frame.columns = [str(column).strip() for column in frame.columns]
        return frame

    @staticmethod
    def _valid_war_frame(frame: pd.DataFrame) -> bool:
        columns = {str(column).strip() for column in frame.columns}
        if "WAR" not in columns:
            return False
        if not ({"year_ID", "year_id"} & columns):
            return False
        return bool({"mlb_ID", "mlb_id", "mlbID", "player_ID", "name_common"} & columns)

    @staticmethod
    def _classify(member_name: str, frame: pd.DataFrame) -> str | None:
        lower_name = member_name.casefold()
        columns = {str(column).strip().casefold() for column in frame.columns}

        if "pitch" in lower_name:
            return "pitching"
        if "bat" in lower_name:
            return "batting"

        pitching_markers = {
            "era_plus",
            "era+",
            "ipruns",
            "ra9opp",
            "xra",
            "waa_adj",
        }
        batting_markers = {
            "ops_plus",
            "ops+",
            "runs_above_avg_off",
            "runs_batting",
            "runs_br",
        }
        pitch_score = len(columns & pitching_markers)
        bat_score = len(columns & batting_markers)
        if pitch_score > bat_score:
            return "pitching"
        if bat_score > pitch_score:
            return "batting"

        # Last-resort structural hints used by B-Ref's published WAR schemas.
        if "ipruns" in columns or ("gs" in columns and "ra" in columns):
            return "pitching"
        if "pa" in columns:
            return "batting"
        return None

    @staticmethod
    def _date_from_name(value: str) -> str:
        match = re.search(r"(20\d{2}-\d{2}-\d{2})", value)
        return match.group(1) if match else ""

    @staticmethod
    def _atomic_write_csv(frame: pd.DataFrame, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{destination.stem}.", suffix=".tmp", dir=destination.parent
        )
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            frame.to_csv(temp_path, index=False, encoding="utf-8")
            os.replace(temp_path, destination)
        finally:
            temp_path.unlink(missing_ok=True)

    @staticmethod
    def _atomic_write_json(payload: dict[str, object], destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{destination.stem}.", suffix=".tmp", dir=destination.parent
        )
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            temp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            os.replace(temp_path, destination)
        finally:
            temp_path.unlink(missing_ok=True)
