from __future__ import annotations

from config.i18n import tr, tr_list

from typing import Any

from PyQt6.QtCore import QStringListModel, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (QCompleter, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QProgressBar, QPushButton, QScrollArea, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget)

from models.player import PlayerBundle


class CompareView(QWidget):
    search_requested = pyqtSignal(int, str)
    player_selected = pyqtSignal(int, int)
    MAX_PLAYERS = 4

    def __init__(self) -> None:
        super().__init__()
        self._bundles = {i: None for i in range(4)}
        self._league_positions: dict[int, dict[str, Any]] = {}
        self._search_maps = {i: {} for i in range(4)}
        self._search_models, self._completers, self._timers = {}, {}, {}
        self._searches, self._name_labels, self._profile_labels, self._panes = {}, {}, {}, {}
        root = QVBoxLayout(self)
        title = QLabel(tr("Compare Players")); title.setObjectName("title"); root.addWidget(title)
        sub = QLabel(tr("2~4명의 선수를 비교합니다. 원시 지표, 리그 내 위치, 선택 선수 간 강점을 함께 표시합니다."))
        sub.setObjectName("subtitle"); sub.setWordWrap(True); root.addWidget(sub)
        tools = QHBoxLayout(); tools.addStretch(); self.add_button = QPushButton(tr("+ 선수 추가"))
        self.add_button.clicked.connect(self._add_slot); tools.addWidget(self.add_button); root.addLayout(tools)
        grid = QGridLayout(); root.addLayout(grid)
        for slot in range(4):
            pane = self._build_pane(slot); self._panes[slot] = pane; grid.addWidget(pane, slot // 2, slot % 2)
            pane.setVisible(slot < 2)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.table = QTableWidget(0, 3); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True); self.table.verticalHeader().setVisible(False); split.addWidget(self.table)
        box = QGroupBox(tr("Comparison Insights")); box.setMinimumWidth(430); outer = QVBoxLayout(box)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.Shape.NoFrame); outer.addWidget(scroll)
        content = QWidget(); self.insights = QVBoxLayout(content); self.insights.setSpacing(10); scroll.setWidget(content)
        split.addWidget(box); split.setSizes([650, 650]); root.addWidget(split, 1)
        self._render()

    def _build_pane(self, slot: int) -> QWidget:
        pane = QWidget(); lay = QVBoxLayout(pane); lay.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout(); row.addWidget(QLabel(tr(f"Player {chr(65+slot)}"))); row.addStretch()
        if slot >= 2:
            b = QPushButton(tr("제거")); b.clicked.connect(lambda _=False, s=slot: self._remove_slot(s)); row.addWidget(b)
        lay.addLayout(row)
        search = QLineEdit(); search.setPlaceholderText(tr("Search player (e.g. Judge)")); lay.addWidget(search)
        model = QStringListModel(self); comp = QCompleter(model, self); comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setCompletionMode(QCompleter.CompletionMode.PopupCompletion); search.setCompleter(comp)
        name = QLabel(tr("No player selected")); name.setObjectName("title"); profile = QLabel(tr("—")); profile.setObjectName("subtitle")
        lay.addWidget(name); lay.addWidget(profile)
        timer = QTimer(self); timer.setSingleShot(True); timer.setInterval(350); timer.timeout.connect(lambda s=slot: self._emit_search(s))
        search.textChanged.connect(lambda _t, s=slot: self._timers[s].start()); search.returnPressed.connect(lambda s=slot: self._enter(s))
        comp.activated[str].connect(lambda label, s=slot: self._completion(s, label))
        self._searches[slot], self._search_models[slot], self._completers[slot], self._timers[slot] = search, model, comp, timer
        self._name_labels[slot], self._profile_labels[slot] = name, profile
        return pane

    def _visible(self): return [i for i in range(4) if self._panes[i].isVisible()]
    def _selected(self): return [i for i in self._visible() if self._bundles[i] is not None]
    def _add_slot(self):
        for i in (2, 3):
            if not self._panes[i].isVisible(): self._panes[i].show(); break
        self.add_button.setEnabled(any(not self._panes[i].isVisible() for i in (2, 3))); self._render()
    def _remove_slot(self, slot):
        self._bundles[slot] = None; self._league_positions.pop(slot, None); self._search_maps[slot] = {}; self._search_models[slot].setStringList([])
        self._searches[slot].clear(); self._name_labels[slot].setText(tr("No player selected")); self._profile_labels[slot].setText(tr("—"))
        self._panes[slot].hide(); self.add_button.setEnabled(True); self._render()
    def current_query(self, slot): return self._searches.get(slot).text().strip() if slot in self._searches else ""
    def update_search_results(self, slot, rows):
        if slot not in self._search_maps: return
        mapping = {}
        for r in rows:
            name = str(r.get("name", "")); team = str(r.get("team", "")); pos = str(r.get("position", "")); pid = int(r.get("id", 0) or 0)
            if name and pid: mapping[f"{name} — {team} {pos}".strip()] = pid
        self._search_maps[slot] = mapping; self._search_models[slot].setStringList(list(mapping))
        if mapping and self._searches[slot].hasFocus(): self._completers[slot].complete()
    def set_loading(self, slot, player_id):
        if slot in self._name_labels: self._league_positions.pop(slot, None); self._name_labels[slot].setText(tr(f"Loading player {player_id}…"))
    def set_player(self, slot, bundle):
        if slot not in self._bundles: return
        self._bundles[slot] = bundle; p = bundle.profile; self._name_labels[slot].setText(tr(p.full_name))
        self._profile_labels[slot].setText(tr(f"{p.team or '—'} | {p.position or '—'} | {'Pitcher' if p.is_pitcher else 'Hitter'} | Age {p.age or '—'}")); self._render()
    def set_league_context(self, slot, payload): self._league_positions.__setitem__(slot, payload or {}); self._render_insights()
    def _emit_search(self, slot):
        if slot in self._visible() and len(self.current_query(slot)) >= 2: self.search_requested.emit(slot, self.current_query(slot))
    def _completion(self, slot, label):
        pid = self._search_maps.get(slot, {}).get(label)
        if pid: self.player_selected.emit(slot, pid)
    def _enter(self, slot):
        q = self.current_query(slot).casefold()
        for label, pid in self._search_maps.get(slot, {}).items():
            if label.casefold().startswith(q): self.player_selected.emit(slot, pid); return

    @staticmethod
    def _labels_for(*bundles):
        actual = [b for b in bundles if b]
        if not actual: return ["Select two players to compare"]
        flags = [b.profile.is_pitcher for b in actual]
        if all(flags): return ["ERA","WHIP","FIP","xFIP","K%","BB%","fWAR","bWAR","ERA+","xERA","xBA","xSLG","xwOBA","Whiff %","Chase %","Avg EV Allowed"]
        if not any(flags): return ["AVG","OBP","SLG","OPS","HR","RBI","SB","PA","fWAR","bWAR","wRC+","OPS+","ISO","BABIP","BB%","K%","wOBA","Avg EV","Max EV","Hard Hit %","Barrel %","xBA","xSLG","xwOBA","OAA","Runs Prevented","Sprint Speed"]
        return ["fWAR","bWAR","BB%","K%","xBA","xSLG","xwOBA"]

    @classmethod
    def _metric_value(cls, b, label):
        if b is None: return None
        basic, fg, br, sc, d = b.basic, b.fangraphs, b.bref, b.statcast, b.defense
        if b.profile.is_pitcher:
            bf=cls._num(basic.get("battersFaced")); so=cls._num(basic.get("strikeOuts")); bb=cls._num(basic.get("baseOnBalls"))
            return {"ERA":basic.get("era",fg.get("ERA")),"WHIP":basic.get("whip",fg.get("WHIP")),"FIP":fg.get("FIP"),"xFIP":fg.get("xFIP"),"K%":so/bf*100 if bf else fg.get("K%"),"BB%":bb/bf*100 if bf else fg.get("BB%"),"fWAR":fg.get("fWAR"),"bWAR":br.get("bWAR"),"ERA+":br.get("ERA+"),"xERA":sc.get("xERA"),"xBA":sc.get("xBA"),"xSLG":sc.get("xSLG"),"xwOBA":sc.get("xwOBA"),"Whiff %":sc.get("Whiff %"),"Chase %":sc.get("Chase %"),"Avg EV Allowed":sc.get("Average Exit Velocity Allowed")}.get(label)
        return {"AVG":basic.get("avg",fg.get("AVG")),"OBP":basic.get("obp",fg.get("OBP")),"SLG":basic.get("slg",fg.get("SLG")),"OPS":basic.get("ops",fg.get("OPS")),"HR":basic.get("homeRuns",fg.get("HR")),"RBI":basic.get("rbi",fg.get("RBI")),"SB":basic.get("stolenBases",fg.get("SB")),"PA":basic.get("plateAppearances",fg.get("PA")),"fWAR":fg.get("fWAR"),"bWAR":br.get("bWAR"),"wRC+":fg.get("wRC+"),"OPS+":br.get("OPS+"),"ISO":fg.get("ISO"),"BABIP":fg.get("BABIP"),"BB%":fg.get("BB%"),"K%":fg.get("K%"),"wOBA":fg.get("wOBA"),"Avg EV":sc.get("Average Exit Velocity"),"Max EV":sc.get("Max Exit Velocity"),"Hard Hit %":sc.get("Hard Hit %"),"Barrel %":sc.get("Barrel %"),"xBA":sc.get("xBA"),"xSLG":sc.get("xSLG"),"xwOBA":sc.get("xwOBA"),"OAA":d.get("OAA"),"Runs Prevented":d.get("Runs Prevented"),"Sprint Speed":sc.get("Sprint Speed Value",sc.get("Sprint Speed"))}.get(label)
    @staticmethod
    def _num(v):
        try: return float(str(v).replace("%","").split()[0])
        except (TypeError,ValueError,IndexError): return 0.0
    @classmethod
    def _format_metric(cls, label, v):
        if v is None: return "—"
        n=cls._num(v)
        if label=="OAA": return str(int(round(n)))
        if label=="Sprint Speed": return f"{n:.1f} ft/s"
        if isinstance(v,float): return f"{v:.3f}" if abs(v)<1 else f"{v:.2f}"
        return str(v)
    @classmethod
    def _format(cls,v): return cls._format_metric("",v)

    def _render(self):
        slots=self._visible(); bundles=[self._bundles[i] for i in slots]; labels=self._labels_for(*bundles)
        self.table.setColumnCount(1+len(slots)); self.table.setHorizontalHeaderLabels(tr_list(["Metric"]+[self._bundles[i].profile.full_name if self._bundles[i] else f"Player {chr(65+i)}" for i in slots])); self.table.setRowCount(len(labels))
        for r,label in enumerate(labels):
            self.table.setItem(r,0,QTableWidgetItem(tr(label))); self.table.item(r,0).setData(Qt.ItemDataRole.UserRole, label)
            for c,b in enumerate(bundles,1): self.table.setItem(r,c,QTableWidgetItem(tr(self._format_metric(label,self._metric_value(b,label)))))
        self.table.resizeColumnsToContents(); self._render_insights()

    @staticmethod
    def _clear(layout):
        while layout.count():
            item=layout.takeAt(0); w=item.widget()
            if w: w.deleteLater()
    def _render_insights(self):
        self._clear(self.insights)
        h=QLabel(tr("League Position")); h.setObjectName("sectionTitle"); self.insights.addWidget(h)
        note=QLabel(tr("선택 시즌 실제 리그 분포 기준 · AVG/wRC+: FanGraphs qualified hitters · Sprint Speed/OAA: Baseball Savant")); note.setObjectName("subtitle"); note.setWordWrap(True); self.insights.addWidget(note)
        hitters=[i for i in self._selected() if not self._bundles[i].profile.is_pitcher]
        for metric in ("AVG","wRC+","Sprint Speed","OAA"):
            card=QGroupBox(tr(metric)); lay=QVBoxLayout(card)
            for i in hitters:
                b=self._bundles[i]; data=self._league_positions.get(i,{}).get(metric,{}) or {}; pct=data.get("percentile"); value=data.get("value",self._metric_value(b,metric))
                row=QHBoxLayout(); name=QLabel(tr(b.profile.full_name)); name.setMinimumWidth(120); row.addWidget(name)
                bar=QProgressBar(); bar.setRange(0,100); bar.setValue(int(round(pct)) if pct is not None else 0); bar.setFormat(f"{int(round(pct))}th" if pct is not None else "불러오는 중…"); row.addWidget(bar,1)
                val=QLabel(tr(self._format_metric(metric,value))); val.setMinimumWidth(72); val.setAlignment(Qt.AlignmentFlag.AlignRight); row.addWidget(val); lay.addLayout(row)
            self.insights.addWidget(card)
        h=QLabel(tr("Head-to-Head")); h.setObjectName("sectionTitle"); self.insights.addWidget(h)
        actual=[self._bundles[i] for i in self._selected()]
        if len(actual)<2: self.insights.addWidget(QLabel(tr("두 명 이상의 선수를 불러오면 비교 요약이 표시됩니다."))); return
        if len({b.profile.is_pitcher for b in actual})>1: self.insights.addWidget(QLabel(tr("타자와 투수의 역할별 카테고리 우열은 계산하지 않습니다."))); return
        cats=(('Contact',(('AVG',True),('xBA',True),('K%',False))),('Power',(('SLG',True),('ISO',True),('Barrel %',True),('Hard Hit %',True))),('Discipline',(('BB%',True),('K%',False))),('Speed',(('Sprint Speed',True),('SB',True))),('Defense',(('OAA',True),('Runs Prevented',True))),('Overall',(('wRC+',True),('OPS',True),('fWAR',True),('bWAR',True)))) if not actual[0].profile.is_pitcher else (('Run Prevention',(('ERA',False),('FIP',False),('xERA',False),('ERA+',True))),('Dominance',(('K%',True),('Whiff %',True))),('Command',(('BB%',False),('WHIP',False),('Chase %',True))),('Overall',(('fWAR',True),('bWAR',True))))
        for cat,metrics in cats:
            scores={i:0.0 for i in range(len(actual))}; counts={i:0 for i in scores}
            for metric,higher in metrics:
                vals={i:self._num(self._metric_value(b,metric)) for i,b in enumerate(actual) if self._metric_value(b,metric) is not None}
                for rank,(i,_v) in enumerate(sorted(vals.items(),key=lambda x:x[1],reverse=higher)):
                    scores[i]+=len(vals)-rank; counts[i]+=1
            valid={i:scores[i]/counts[i] for i in scores if counts[i]}; card=QGroupBox(tr(cat)); lay=QVBoxLayout(card)
            if valid:
                best=max(valid,key=valid.get); win=QLabel(tr(f"우세: {actual[best].profile.full_name}")); win.setObjectName("insightWinner"); lay.addWidget(win)
                order=sorted(valid,key=valid.get,reverse=True)
                for rank,i in enumerate(order,1): lay.addWidget(QLabel(tr(f"{actual[i].profile.full_name}   #{rank} · {valid[i]:.1f} points")))
            self.insights.addWidget(card)
        self.insights.addStretch()
