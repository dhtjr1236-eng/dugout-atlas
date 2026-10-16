"""Pitch distributions and descriptive splits, using runtime-validated fields only."""
from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd

from services.statcast_service import SWING_DESCRIPTIONS, WHIFF_DESCRIPTIONS


def analyze_pitches(frame: pd.DataFrame, player_id: int, season: int) -> dict[str, Any]:
    """Return summaries only. Missing values never become zero observations."""
    result: dict[str, Any] = dict(player_id=player_id, season=season, status='empty',
                                 profile=[], matchup={}, quality={}, total=0)
    if frame is None or frame.empty:
        return result
    if 'pitcher' not in frame or not pd.to_numeric(frame.pitcher, errors='coerce').eq(player_id).all():
        raise ValueError('Pitcher identity could not be verified')
    required = {'pitch_type', 'game_date', 'game_type'}
    if not required.issubset(frame.columns):
        result.update(status='unverified', reason='Identity/date/game type fields missing')
        return result
    dates = pd.to_datetime(frame.game_date, errors='coerce')
    work = frame.loc[dates.dt.year.eq(season) & frame.game_type.eq('R')].copy().reset_index(drop=True)
    result['total'] = len(work)
    if work.empty:
        return result
    codes = work.pitch_type.astype('string').str.strip()
    known = codes.notna() & codes.ne('')
    result['unknown_pitch'] = int((~known).sum())
    work = work.loc[known].copy()
    work['pitch_type'] = codes.loc[known]
    for field in ('release_speed', 'release_spin_rate'):
        if field not in work:
            result['quality'][field] = {'status': 'unverified', 'valid': 0, 'total': len(work)}
            continue
        values = pd.to_numeric(work[field], errors='coerce')
        valid = values.notna() & np.isfinite(values) & values.gt(0)
        result['quality'][field] = {'status': 'verified', 'valid': int(valid.sum()), 'total': len(work)}
        for code, group in work.groupby('pitch_type', sort=True):
            v = values.loc[group.index][valid.loc[group.index]]
            row = dict(pitch=str(code), field=field, n=len(v), total=len(group),
                       missing=len(group)-len(v), small=len(v)<30)
            if not v.empty:
                q = v.quantile([.1,.25,.5,.75,.9])
                row.update(p10=float(q.loc[.1]), q1=float(q.loc[.25]), median=float(q.loc[.5]),
                           q3=float(q.loc[.75]), p90=float(q.loc[.9]), iqr=float(q.loc[.75]-q.loc[.25]),
                           sd=float(v.std(ddof=1)) if len(v)>1 else None,
                           minimum=float(v.min()), maximum=float(v.max()))
            result['profile'].append(row)
    for mode, fields in [('hand', ['stand']), ('count', ['balls','strikes'])]:
        if not all(f in work for f in fields):
            result['matchup'][mode] = {'status':'unverified','rows':[]}
            continue
        subset = work.copy()
        if mode == 'hand':
            mask = subset.stand.isin(['L','R'])
            subset['condition'] = subset.stand
        else:
            b=pd.to_numeric(subset.balls,errors='coerce'); s=pd.to_numeric(subset.strikes,errors='coerce')
            mask=b.isin([0,1,2,3]) & s.isin([0,1,2])
            subset['condition'] = b.where(mask).astype('Int64').astype('string')+'-'+s.where(mask).astype('Int64').astype('string')
        subset=subset.loc[mask]
        rows=[]
        for condition, group in subset.groupby('condition',sort=True):
            denominator=len(group)
            for code, pitches in group.groupby('pitch_type',sort=True):
                swings=whiffs=None
                outcome_n=0
                if 'description' in pitches:
                    valid=pitches.description.notna() & pitches.description.astype('string').str.strip().ne('')
                    outcome_n=int(valid.sum())
                    if outcome_n:
                        swings=int(pitches.loc[valid,'description'].isin(SWING_DESCRIPTIONS).sum())
                        whiffs=int(pitches.loc[valid,'description'].isin(WHIFF_DESCRIPTIONS).sum())
                rows.append(dict(condition=str(condition),pitch=str(code),pitches=len(pitches),
                                 denominator=denominator,usage=100*len(pitches)/denominator,
                                 swings=swings,whiffs=whiffs,outcome_n=outcome_n,
                                 whiff=100*whiffs/swings if swings else None,
                                 small=denominator<30 or swings is None or swings<30 or outcome_n<len(pitches)))
        result['matchup'][mode]={'status':'ready' if rows else 'empty','rows':rows,
                                'valid':len(subset),'total':len(work)}
    if not result['profile']:
        result['status']='unverified'
    elif not any(r['n'] for r in result['profile']):
        result['status']='empty'
    else:
        complete=all(q['status']=='verified' for q in result['quality'].values())
        result['status']='ready' if complete and all(r['n']>=30 and r['missing']==0 for r in result['profile']) else 'partial'
    return result

# Dugout Atlas
# Copyright (c) 2026 dhtjr1236-eng
# Unauthorized redistribution or rebranding is prohibited.
