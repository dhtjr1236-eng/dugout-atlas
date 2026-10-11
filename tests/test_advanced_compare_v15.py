from __future__ import annotations

from services.advanced_compare_service import percentile

def test_advanced_compare_percentile() -> None:
    assert percentile(3.0,[1.0,2.0,3.0,4.0]) == 75.0
    assert percentile(None,[1.0]) is None

# Dugout Atlas
# Copyright (c) 2026 dhtjr1236-eng
# Unauthorized redistribution or rebranding is prohibited.
