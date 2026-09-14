from __future__ import annotations

import json

import pandas as pd
import pytest


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
