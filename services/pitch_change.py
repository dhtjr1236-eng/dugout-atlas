"""Descriptive before/after summaries. No movement estimates or persistent storage."""
from __future__ import annotations

from datetime import date
from typing import Any
import numpy as np
import pandas as pd

METRICS = {'release_speed': 'mph', 'release_spin_rate': 'rpm'}
MIN_SAMPLE = 30


def metric_summary(frame: pd.DataFrame, field: str) -> dict[str, Any]:
    """Partition every row into valid, missing, or invalid/excluded values."""
    total = len(frame)
    if field not in frame:
        return dict(status='unavailable', n=0, missing=total, excluded=0,
                    total=total, median=None, iqr=None, small=True)
    raw = frame[field]
    missing = raw.isna() | raw.astype('string').str.strip().eq('').fillna(False)
    values = pd.to_numeric(raw, errors='coerce')
    valid = values.notna() & np.isfinite(values) & values.gt(0)
    v = values.loc[valid]
    n = len(v)
    return dict(status='unavailable' if not n else 'partial' if n < total or n < MIN_SAMPLE else 'ready',
                n=n, missing=int(missing.sum()), excluded=int((~missing & ~valid).sum()), total=total,
                median=float(v.median()) if n else None,
                iqr=float(v.quantile(.75)-v.quantile(.25)) if n else None, small=n < MIN_SAMPLE)


def analyze_change(frame: pd.DataFrame, player_id: int, season: int,
                   cutoff: str, cadence: str = 'daily') -> dict[str, Any]:
    """Split on game_date; the cutoff date belongs to after. Return aggregates only."""
    boundary = date.fromisoformat(cutoff)
    if boundary.year != season or cadence not in ('daily', 'weekly'):
        raise ValueError('Invalid season, cutoff or cadence')
    result = dict(player_id=player_id, season=season, cutoff=cutoff, cadence=cadence,
                  status='empty', raw_rows=0, total=0, classified=0, unclassified=0,
                  excluded_rows=0, pitches=[], observed_start=None, observed_end=None,
                  movement={'IVB': 'unverified', 'HB': 'unverified'})
    if frame is None or frame.empty:
        return result
    result['raw_rows'] = len(frame)
    if 'pitcher' not in frame or not pd.to_numeric(frame.pitcher, errors='coerce').eq(player_id).all():
        raise ValueError('Pitcher identity could not be verified')
    if not {'game_date', 'game_type', 'pitch_type'}.issubset(frame.columns):
        result.update(status='unavailable', excluded_rows=len(frame))
        return result
    work = frame.reset_index(drop=True).copy()
    dates = pd.to_datetime(work.game_date, format='ISO8601', errors='coerce')
    keep = dates.dt.year.eq(season) & work.game_type.eq('R')
    result['excluded_rows'] = int((~keep).sum())
    work = work.loc[keep].copy()
    work['_date'] = dates.loc[keep].dt.normalize()
    result['total'] = len(work)
    if work.empty:
        return result
    result['observed_start'] = work._date.min().date().isoformat()
    result['observed_end'] = work._date.max().date().isoformat()
    codes = work.pitch_type.astype('string').str.strip()
    known = codes.notna() & codes.ne('')
    result['classified'] = int(known.sum())
    result['unclassified'] = int((~known).sum())
    work = work.loc[known].copy()
    work['pitch_type'] = codes.loc[known]
    for code, group in work.groupby('pitch_type', sort=True):
        before = group.loc[group._date.lt(pd.Timestamp(boundary))]
        after = group.loc[group._date.ge(pd.Timestamp(boundary))]
        row = dict(pitch=str(code), before_n=len(before), after_n=len(after), metrics={})
        for field, unit in METRICS.items():
            a, b = metric_summary(before, field), metric_summary(after, field)
            points = []
            keys = group._date if cadence == 'daily' else group._date.dt.to_period('W-SUN').dt.start_time
            for day, part in group.groupby(keys):
                points.append(dict(date=day.date().isoformat(), **metric_summary(part, field)))
            row['metrics'][field] = dict(unit=unit, before=a, after=b, points=points,
                delta_median=b['median']-a['median'] if a['median'] is not None and b['median'] is not None else None,
                delta_iqr=b['iqr']-a['iqr'] if a['iqr'] is not None and b['iqr'] is not None else None)
        result['pitches'].append(row)
    if result['pitches'] and not any(field in work for field in METRICS):
        result['status'] = 'unavailable'
    if any(m[side]['n'] for r in result['pitches'] for m in r['metrics'].values() for side in ('before','after')):
        # Movement remains explicitly unavailable, so the overall result is partial.
        result['status'] = 'partial'
    return result

# Dugout Atlas
# Copyright (c) 2026 dhtjr1236-eng
# Unauthorized redistribution or rebranding is prohibited.
