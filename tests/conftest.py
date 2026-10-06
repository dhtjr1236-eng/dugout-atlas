from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

# Set paths before test collection imports config.settings; never touch real profiles.
_TEST_PROFILE = tempfile.TemporaryDirectory(prefix="dugout-tests-")
for _name in ("HOME", "USERPROFILE", "LOCALAPPDATA", "XDG_CONFIG_HOME"):
    os.environ[_name] = str(Path(_TEST_PROFILE.name) / _name)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


import pandas as pd
import pytest

# Isolate legacy QSettings as well as the runtime root before collection imports.
from PyQt6.QtCore import QSettings
from config import preferences as _preferences

def _collection_store():
    return QSettings(str(Path(_TEST_PROFILE.name) / "settings.ini"), QSettings.Format.IniFormat)

_preferences.store = _collection_store
_collection_settings = _collection_store()
_collection_settings.setValue("preferences/data_root", str(Path(_TEST_PROFILE.name) / "runtime"))
_collection_settings.sync()


@pytest.fixture(autouse=True)
def _legacy_fangraphs_history_transport(request, monkeypatch):
    """Keep the pre-v1.0.6 transport regression test aligned with the JSON client.

    The old test monkeypatches a module-level ``sync_get_text`` symbol that no longer
    exists after FanGraphs moved to its dedicated JSON/mobile-UA transport. Restrict
    this compatibility shim to that one legacy test so production code and all newer
    FanGraphs tests continue to exercise ``_request_json`` normally.
    """
    if request.node.name != "test_fangraphs_history_uses_correct_start_end_params":
        yield
        return

    import services.fangraphs_service as fg_module
    from services.fangraphs_service import FG_LEADERS_URL, FanGraphsService

    monkeypatch.setattr(
        fg_module,
        "sync_get_text",
        lambda _url, params=None: json.dumps({"data": []}),
        raising=False,
    )

    def compat_fetch(
        self,
        start: int,
        end: int,
        pitcher: bool,
        *,
        start_date: str = "",
        end_date: str = "",
        ind: int = 1,
    ) -> pd.DataFrame:
        params = self._api_params(
            start,
            end,
            pitcher,
            start_date=start_date,
            end_date=end_date,
            ind=ind,
        )
        text = fg_module.sync_get_text(FG_LEADERS_URL, params=params)
        payload = json.loads(text)
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        return pd.DataFrame(rows if isinstance(rows, list) else [])

    monkeypatch.setattr(FanGraphsService, "_fetch_api", compat_fetch)
    yield


@pytest.fixture(autouse=True)
def _isolated_preferences(tmp_path, monkeypatch):
    from PyQt6.QtCore import QSettings
    from config import preferences
    monkeypatch.setattr(preferences, "store", lambda: QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat))
