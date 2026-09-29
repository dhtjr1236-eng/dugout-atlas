"""Live acceptance probe: 2 real players x 2 cumulative ranges; no UI/cache writes.
Run from project root: python tools/verify_season_race.py --output race-evidence.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.fangraphs_service import FG_LEADERS_URL, FanGraphsService
from services.season_race import RacePlayer, RaceService, point_from_row, strict_row
import threading


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='race-evidence.json')
    args=parser.parse_args()
    fg=FanGraphsService(None)
    report={'endpoint':FG_LEADERS_URL,'captured_at':datetime.now(UTC).isoformat(),
            'availability':'UNVERIFIED','requests':[]}
    try:
        axis=RaceService(fg).schedule(2025,threading.Event())
        report['season_start']=axis.start
        for player in [RacePlayer(592450,'Aaron Judge','bat',15640),RacePlayer(669373,'Tarik Skubal','pit',22267)]:
            for end in ('2025-05-01','2025-06-01'):
                params=fg._api_params(2025,2025,player.role=='pit',start_date=axis.start,end_date=end,ind=0)
                request={'player':player.name,'mlbam_id':player.mlbam_id,'fg_id':player.fg_id,
                         'role':player.role,'params':params}
                report['requests'].append(request)
                payload=fg._request_json(FG_LEADERS_URL,params)
                row=strict_row(payload.get('data',[]),player)
                if row is None: raise RuntimeError('No matching player row')
                point=point_from_row(row,end,datetime.now(UTC).isoformat())
                request.update(raw_row=row,returned_WAR=row['WAR'],display_value=repr(point.war),
                               match=point.war==row['WAR'])
                print(player.name,end,repr(point.war),flush=True)
                time.sleep(1)
        report['availability']='A' if all(r['match'] for r in report['requests']) else 'UNVERIFIED'
    except Exception as exc:
        report['error']=f'{type(exc).__name__}: {exc}'
    Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Availability:',report['availability'])
    return 0 if report['availability']=='A' else 1

if __name__=='__main__': raise SystemExit(main())
