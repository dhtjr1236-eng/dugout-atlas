"""Pure range and extrema helpers shared by on-screen and exported races."""
from __future__ import annotations

import math
from typing import Iterable, TypeVar

T = TypeVar('T')


def period_extrema(points: Iterable[T], start: str, end: str) -> tuple[T, T] | None:
    """Return high/low over all supplied dates; ties use the earliest date."""
    ordered = sorted((p for p in points if start <= p.day <= end and math.isfinite(p.value)),
                     key=lambda p: p.day)
    if not ordered:
        return None
    return max(ordered, key=lambda p: p.value), min(ordered, key=lambda p: p.value)


def validate_limits(low: float, high: float) -> tuple[float, float]:
    """Reject invalid axes rather than silently reversing or flattening them."""
    if not all(math.isfinite(v) for v in (low, high)) or not 0 <= low < high <= 5:
        raise ValueError('OPS limits must satisfy 0 <= minimum < maximum <= 5.')
    return low, high
