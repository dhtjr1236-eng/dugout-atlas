from __future__ import annotations

import logging
import zipfile

import pytest

from config.logging_config import PrivateDataFilter
from services.base_http import HttpError, _retry_after, _should_retry
from services.bref_local_store import BRefLocalStore


def test_http_retry_policy() -> None:
    assert not _should_retry(HttpError("HTTP 403", status=403))
    assert not _should_retry(HttpError("HTTP 404", status=404))
    assert _should_retry(HttpError("HTTP 429", status=429))
    assert _should_retry(HttpError("HTTP 503", status=503))
    assert _retry_after("120") == 60


def test_private_filter_removes_credentials_and_home() -> None:
    record = logging.LogRecord("test", logging.WARNING, __file__, 1,
                               "GET https://example.org/data?token=secret C:\\Users\\alice\\data token=secret", (), None)
    assert PrivateDataFilter().filter(record)
    assert "secret" not in record.getMessage()
    assert "alice" not in record.getMessage()


def test_bref_archive_rejects_bomb_before_read(tmp_path) -> None:
    archive_path = tmp_path / "war_archive.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("war_daily_bat.csv", "x" * 100_000)
    store = BRefLocalStore(tmp_path / "store")
    with pytest.raises(ValueError, match="safe file count, size or compression ratio"):
        store.import_path(archive_path)


def test_bref_metadata_keeps_only_basename(tmp_path) -> None:
    source = tmp_path / "war_daily_bat.txt"
    source.write_text("name_common,mlb_ID,year_ID,PA,WAR\nA,1,2026,42,1.2\n", encoding="utf-8")
    store = BRefLocalStore(tmp_path / "store")
    result = store.import_path(source)
    assert result.source_file == source.name
    assert store.metadata()["last_source_file"] == source.name
    assert str(tmp_path) not in store.meta_path.read_text(encoding="utf-8")
