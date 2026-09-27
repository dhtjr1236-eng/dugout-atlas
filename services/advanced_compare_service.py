from __future__ import annotations

from typing import Any
import pandas as pd

from services.dataframe_utils import first_existing, row_to_dict
from services.running_metrics import SPRINT_SPEED_URL

EXPECTED_URL="https://baseballsavant.mlb.com/leaderboard/expected_statistics"
CONTACT_URL="https://baseballsavant.mlb.com/leaderboard/statcast"

def _num(value:Any)->float|None:
    try:
        if value is None or value=="":
            return None
        if isinstance(value,str) and value.endswith("%"):
            value=value[:-1]
        return float(value)
    except (TypeError,ValueError):
        return None

def percentile(value:Any,population:list[float])->float|None:
    number=_num(value)
    clean=[x for x in (_num(v) for v in population) if x is not None]
    if number is None or not clean:
        return None
    return 100.0*sum(1 for x in clean if x<=number)/len(clean)

class AdvancedCompareService:
    def __init__(self, player_service) -> None:
        self.players=player_service
        self._dist_cache:dict[int,dict[str,list[float]]]={}

    async def search(self,query:str)->list[dict[str,Any]]:
        return await self.players.search(query)

    async def load(self,player_id:int,season:int):
        return await self.players.get_bundle(player_id,season)

    def _distributions(self,season:int)->dict[str,list[float]]:
        if season in self._dist_cache:
            return self._dist_cache[season]
        out={k:[] for k in ("xwOBA","xBA","xSLG","Avg EV","Sprint Speed")}
        try:
            frame=self.players.statcast._savant_csv(EXPECTED_URL,{
                "type":"batter","year":season,"position":"","team":"",
                "filterType":"pa","min":1,"csv":"true",
            },fallback=None)
            if frame is not None and not frame.empty:
                mapping={"xwOBA":("est_woba","xwoba","x_woba"),"xBA":("est_ba","xba","x_ba"),"xSLG":("est_slg","xslg","x_slg")}
                for metric,cols in mapping.items():
                    col=next((c for c in cols if c in frame.columns),None)
                    if col:
                        out[metric]=pd.to_numeric(frame[col],errors="coerce").dropna().astype(float).tolist()
        except Exception:
            pass
        try:
            frame=self.players.statcast._savant_csv(CONTACT_URL,{
                "type":"batter","year":season,"position":"","team":"","min":1,"csv":"true",
            },fallback=None)
            if frame is not None and not frame.empty:
                col=next((c for c in ("avg_hit_speed","avg_exit_velocity") if c in frame.columns),None)
                if col:
                    out["Avg EV"]=pd.to_numeric(frame[col],errors="coerce").dropna().astype(float).tolist()
        except Exception:
            pass
        try:
            frame=self.players.statcast._savant_csv(SPRINT_SPEED_URL,{
                "min_season":season,"max_season":season,"position":"","team":"","min":1,"csv":"true",
            },fallback=None)
            if frame is not None and not frame.empty:
                col=next((c for c in ("hp_to_1b","sprint_speed","sprint_speed_value") if c in frame.columns),None)
                if col:
                    out["Sprint Speed"]=pd.to_numeric(frame[col],errors="coerce").dropna().astype(float).tolist()
        except Exception:
            pass
        self._dist_cache[season]=out
        return out

    def core_metrics(self,bundle)->dict[str,Any]:
        fg=bundle.fangraphs or {}; sc=bundle.statcast or {}; br=bundle.bref or {}; basic=bundle.basic or {}; defense=bundle.defense or {}
        if bundle.profile.is_pitcher:
            return {
                "fWAR":fg.get("fWAR"),"bWAR":br.get("bWAR"),"ERA":fg.get("ERA",basic.get("era")),
                "FIP":fg.get("FIP"),"xFIP":fg.get("xFIP"),"WHIP":fg.get("WHIP",basic.get("whip")),
                "K%":fg.get("K%"),"BB%":fg.get("BB%"),"xERA":sc.get("xERA"),
            }
        return {
            "AVG":basic.get("avg",fg.get("AVG")),"OBP":basic.get("obp",fg.get("OBP")),"SLG":basic.get("slg",fg.get("SLG")),
            "OPS":basic.get("ops",fg.get("OPS")),"wRC+":fg.get("wRC+"),"fWAR":fg.get("fWAR"),"bWAR":br.get("bWAR"),
            "xBA":sc.get("xBA"),"xSLG":sc.get("xSLG"),"xwOBA":sc.get("xwOBA"),
            "Avg EV":sc.get("Average Exit Velocity"),"Sprint Speed":sc.get("Sprint Speed Value",sc.get("Sprint Speed")),"OAA":defense.get("OAA"),
        }

    def statcast_percentiles(self,bundle,season:int)->dict[str,float|None]:
        if bundle.profile.is_pitcher:
            return {}
        values=self.core_metrics(bundle)
        dists=self._distributions(season)
        return {metric:percentile(values.get(metric),population) for metric,population in dists.items() if population}

    @staticmethod
    def sources(bundle)->list[str]:
        names:list[str]=[]
        for payload in (bundle.fangraphs,bundle.bref,bundle.statcast,bundle.defense):
            if not isinstance(payload,dict): continue
            src=payload.get("_source")
            if isinstance(src,dict) and src.get("name"): names.append(str(src["name"]))
            for item in payload.get("_sources",[]) if isinstance(payload.get("_sources"),list) else []:
                if isinstance(item,dict) and item.get("name"): names.append(str(item["name"]))
        return list(dict.fromkeys(names))
