from __future__ import annotations

import logging
import threading
from typing import Any
import pandas as pd
from services.fangraphs_service import FG_LEADERS_URL
from services.running_metrics import SPRINT_SPEED_URL

LOGGER=logging.getLogger(__name__)
_LOCK=threading.RLock(); _CACHE:dict[int,dict[str,list[float]]]={}
OAA_URL="https://baseballsavant.mlb.com/leaderboard/outs_above_average"

def _float(v):
    try: return float(str(v).strip().replace("%","").replace(",","").split()[0])
    except (TypeError,ValueError,IndexError): return None

def percentile(value,population):
    v=_float(value); clean=[x for x in (_float(i) for i in population) if x is not None]
    if v is None or not clean: return None
    return max(0.0,min(100.0,sum(1 for x in clean if x<=v)/len(clean)*100.0))

def _series(frame,aliases):
    wanted={''.join(c for c in a.casefold() if c.isalnum()) for a in aliases}
    for col in frame.columns:
        if ''.join(c for c in str(col).casefold() if c.isalnum()) in wanted:
            return [float(x) for x in pd.to_numeric(frame[col],errors="coerce").dropna().tolist()]
    return []

def distributions(service,season):
    with _LOCK:
        if season in _CACHE: return _CACHE[season]
    out={"AVG":[],"wRC+":[],"Sprint Speed":[],"OAA":[]}
    try:
        p=service.fangraphs._api_params(season,season,False); p.update({"qual":"y","pageitems":"10000","pagenum":"1"})
        data=service.fangraphs._request_json(FG_LEADERS_URL,p); f=pd.DataFrame(data.get("data",[]) if isinstance(data,dict) else [])
        out["AVG"]=_series(f,("AVG",)); out["wRC+"]=_series(f,("wRC+","wRC_plus","wrcplus"))
    except Exception: LOGGER.exception("Compare FanGraphs distribution failed")
    try:
        f=service.statcast._savant_csv(SPRINT_SPEED_URL,{"min_season":season,"max_season":season,"position":"","team":"","min":1,"csv":"true"},fallback=None)
        out["Sprint Speed"]=_series(f,("sprint_speed","sprint speed","sprint_speed_ft_sec","sprint speed (ft / sec)"))
    except Exception: LOGGER.exception("Compare Sprint Speed distribution failed")
    try:
        f=service.statcast._savant_csv(OAA_URL,{"type":"Fielder","startYear":season,"endYear":season,"split":"no","team":"","range":"year","min":1,"pos":"","roles":"","viz":"hide","csv":"true"},fallback=None)
        out["OAA"]=_series(f,("outs_above_average","n_outs_above_average","oaa"))
    except Exception: LOGGER.exception("Compare OAA distribution failed")
    with _LOCK: _CACHE[season]=out
    return out

def player_league_position(service,bundle,season):
    if bundle.profile.is_pitcher: return {}
    pops=distributions(service,season); values={"AVG":bundle.basic.get("avg",bundle.fangraphs.get("AVG")),"wRC+":bundle.fangraphs.get("wRC+"),"Sprint Speed":bundle.statcast.get("Sprint Speed Value",bundle.statcast.get("Sprint Speed")),"OAA":bundle.defense.get("OAA")}
    return {k:{"value":v,"percentile":percentile(v,pops.get(k,[])),"population":len(pops.get(k,[]))} for k,v in values.items()}

def install_compare_league_position():
    from controllers.app_controller import AppController
    if getattr(AppController,"_compare_league_position_installed",False): return
    old_init=AppController.__init__
    def new_init(self,window,db):
        old_init(self,window,db)
        for i in range(4): self._compare_request_ids.setdefault(i,0)
    def load(self,slot,player_id):
        if slot not in self._compare_request_ids: return
        self._compare_request_ids[slot]+=1; req=self._compare_request_ids[slot]; season=self.season
        self.window.compare_view.set_loading(slot,player_id)
        async def task(): return await self.players.get_bundle(player_id,season)
        def success(bundle):
            if self._compare_request_ids.get(slot)!=req: return
            self.window.compare_view.set_player(slot,bundle); self.window.set_busy(f"Compare loaded: {bundle.profile.full_name}")
            if bundle.profile.is_pitcher: return
            def league_task(): return player_league_position(self.players,bundle,season)
            def league_success(payload):
                if self._compare_request_ids.get(slot)==req: self.window.compare_view.set_league_context(slot,payload)
            self._run(league_task,league_success,on_error=lambda m: LOGGER.warning("League Position unavailable: %s",m.splitlines()[-1] if m else "unknown"))
        self._run(task,success)
    AppController.__init__=new_init; AppController.load_compare_player=load; AppController._compare_league_position_installed=True
