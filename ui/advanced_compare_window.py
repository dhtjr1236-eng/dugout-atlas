from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QCompleter,QGroupBox,QHBoxLayout,QHeaderView,QLabel,QLineEdit,QMainWindow,
    QPushButton,QScrollArea,QSpinBox,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget,QStringListModel
)

from config.i18n import tr
from services.advanced_compare_service import AdvancedCompareService
from services.player_name_localization import localized_player_name
from workers.qt_worker import TaskThread

@dataclass
class Slot:
    box:QGroupBox
    edit:QLineEdit
    model:QStringListModel
    completer:QCompleter
    status:QLabel
    mapping:dict[str,int]
    bundle:Any=None

class AdvancedCompareWindow(QMainWindow):
    def __init__(self,player_service,season:int,parent=None)->None:
        super().__init__(parent)
        self.service=AdvancedCompareService(player_service)
        self._threads:set[TaskThread]=set()
        self.slots:list[Slot]=[]
        self.setWindowTitle(tr("Advanced Compare"))
        self.resize(1500,900)
        central=QWidget(); self.setCentralWidget(central)
        root=QVBoxLayout(central)

        top=QHBoxLayout()
        self.title=QLabel(tr("Advanced Compare")); self.title.setObjectName("title")
        self.subtitle=QLabel(tr("Compare 2–4 players in a separate window. The existing Compare tab and main window remain unchanged."))
        self.subtitle.setObjectName("subtitle")
        titlecol=QVBoxLayout(); titlecol.addWidget(self.title); titlecol.addWidget(self.subtitle)
        top.addLayout(titlecol); top.addStretch()
        self.season_label=QLabel(tr("Season")); top.addWidget(self.season_label)
        self.season=QSpinBox(); self.season.setRange(2002,2100); self.season.setValue(season); top.addWidget(self.season)
        self.add_button=QPushButton(tr("+ Add Player")); self.add_button.clicked.connect(self._add_slot); top.addWidget(self.add_button)
        root.addLayout(top)

        self.slot_row=QHBoxLayout(); root.addLayout(self.slot_row)
        self.message=QLabel(tr("Select 2 players to display the advanced comparison report.")); self.message.setObjectName("subtitle")
        root.addWidget(self.message)

        scroll=QScrollArea(); scroll.setWidgetResizable(True)
        content=QWidget(); self.report=QVBoxLayout(content)
        self.core_group=QGroupBox(tr("A. Basic Comparison")); core_layout=QVBoxLayout(self.core_group)
        self.core_table=QTableWidget(0,1); core_layout.addWidget(self.core_table); self.report.addWidget(self.core_group)
        self.stat_group=QGroupBox(tr("B. Statcast Percentile Comparison")); stat_layout=QVBoxLayout(self.stat_group)
        self.stat_table=QTableWidget(0,1); stat_layout.addWidget(self.stat_table); self.report.addWidget(self.stat_group)
        self.footer_group=QGroupBox(tr("Data Range / Sources / Status")); foot=QVBoxLayout(self.footer_group)
        self.footer=QLabel(""); self.footer.setWordWrap(True); foot.addWidget(self.footer); self.report.addWidget(self.footer_group)
        self.report.addStretch(); scroll.setWidget(content); root.addWidget(scroll,1)

        self._add_slot(); self._add_slot()
        self._render()
        self.season.valueChanged.connect(lambda _v:self._reload_selected())

    def _run(self,task,on_success,on_error=None):
        thread=TaskThread(task,self); self._threads.add(thread)
        def cleanup():
            self._threads.discard(thread); thread.deleteLater()
        thread.succeeded.connect(on_success); thread.succeeded.connect(lambda _v:cleanup())
        thread.failed.connect(on_error or (lambda _m:None)); thread.failed.connect(lambda _m:cleanup()); thread.start()

    def _add_slot(self)->None:
        if len(self.slots)>=4: return
        index=len(self.slots)
        box=QGroupBox(tr(f"Player {chr(65+index)}")); layout=QVBoxLayout(box)
        edit=QLineEdit(); edit.setPlaceholderText(tr("Search player (e.g. Judge)"))
        model=QStringListModel(self); comp=QCompleter(model,self); comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive); edit.setCompleter(comp)
        status=QLabel(tr("No player selected")); status.setObjectName("subtitle")
        layout.addWidget(edit); layout.addWidget(status); self.slot_row.addWidget(box,1)
        slot=Slot(box,edit,model,comp,status,{})
        self.slots.append(slot)
        timer=QTimer(edit); timer.setSingleShot(True); timer.setInterval(300)
        edit.textChanged.connect(lambda _t,timer=timer:timer.start())
        timer.timeout.connect(lambda idx=index:self._search(idx))
        comp.activated[str].connect(lambda label,idx=index:self._select(idx,label))
        self.add_button.setEnabled(len(self.slots)<4)

    def _search(self,index:int)->None:
        text=self.slots[index].edit.text().strip()
        if len(text)<2: return
        self._run(lambda:self.service.search(text),lambda rows,idx=index,q=text:self._search_done(idx,q,rows))

    def _search_done(self,index:int,query:str,rows:list[dict[str,Any]])->None:
        slot=self.slots[index]
        if slot.edit.text().strip()!=query:return
        slot.mapping={}; labels=[]
        for row in rows:
            label=f"{row.get('name','')} — {row.get('team','')} {row.get('position','')}".strip()
            slot.mapping[label]=int(row.get("id",0) or 0); labels.append(label)
        slot.model.setStringList(labels)
        if labels: slot.completer.complete()

    def _select(self,index:int,label:str)->None:
        player_id=self.slots[index].mapping.get(label)
        if not player_id:return
        slot=self.slots[index]; slot.status.setText(tr("Loading…"))
        season=self.season.value()
        self._run(lambda:self.service.load(player_id,season),lambda bundle,idx=index:self._loaded(idx,bundle))

    def _loaded(self,index:int,bundle:Any)->None:
        slot=self.slots[index]; slot.bundle=bundle
        slot.status.setText(localized_player_name(bundle.profile.id,bundle.profile.full_name))
        self._render()

    def _reload_selected(self)->None:
        for i,slot in enumerate(self.slots):
            if slot.bundle is not None:
                pid=slot.bundle.profile.id
                self._run(lambda pid=pid:self.service.load(pid,self.season.value()),lambda bundle,idx=i:self._loaded(idx,bundle))

    @staticmethod
    def _format(value:Any)->str:
        if value is None or value=="":return "—"
        if isinstance(value,float): return f"{value:.3f}" if abs(value)<1 else f"{value:.2f}"
        return str(value)

    def _setup_table(self,table:QTableWidget,players:list[Any],first_header:str)->None:
        table.clear()
        table.setColumnCount(1+len(players))
        table.setHorizontalHeaderLabels([first_header]+[localized_player_name(p.profile.id,p.profile.full_name) for p in players])
        h=table.horizontalHeader(); h.setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents)
        for c in range(1,table.columnCount()):h.setSectionResizeMode(c,QHeaderView.ResizeMode.Stretch)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def _render(self)->None:
        players=[s.bundle for s in self.slots if s.bundle is not None]
        if len(players)<2:
            self.core_group.setVisible(False); self.stat_group.setVisible(False); self.footer_group.setVisible(True)
            self.footer.setText(tr("Select 2 players to generate the report.")); return
        self.core_group.setVisible(True)
        metrics=[]
        metric_maps=[self.service.core_metrics(p) for p in players]
        for mapping in metric_maps:
            for key in mapping:
                if key not in metrics:metrics.append(key)
        self._setup_table(self.core_table,players,tr("Metric")); self.core_table.setRowCount(len(metrics))
        for r,metric in enumerate(metrics):
            self.core_table.setItem(r,0,QTableWidgetItem(metric))
            for c,mapping in enumerate(metric_maps,1):self.core_table.setItem(r,c,QTableWidgetItem(self._format(mapping.get(metric))))

        percentiles=[self.service.statcast_percentiles(p,self.season.value()) for p in players]
        pmetrics=[]
        for mapping in percentiles:
            for key in mapping:
                if key not in pmetrics:pmetrics.append(key)
        self.stat_group.setVisible(bool(pmetrics))
        if pmetrics:
            self._setup_table(self.stat_table,players,tr("Savant Percentile")); self.stat_table.setRowCount(len(pmetrics))
            for r,metric in enumerate(pmetrics):
                self.stat_table.setItem(r,0,QTableWidgetItem(metric))
                for c,mapping in enumerate(percentiles,1):
                    value=mapping.get(metric); text="—" if value is None else f"{round(value):.0f}th"
                    self.stat_table.setItem(r,c,QTableWidgetItem(text))

        sources=[]
        for p in players:sources.extend(self.service.sources(p))
        sources=list(dict.fromkeys(sources))
        self.footer_group.setVisible(True)
        self.footer.setText(
            f"{tr('Season')}: {self.season.value()} · {tr('Players')}: {len(players)}\n"
            + f"{tr('Sources')}: {', '.join(sources) if sources else 'MLB / FanGraphs / Baseball-Reference / Baseball Savant'}\n"
            + tr("Status: only provider-returned values are shown; unavailable metrics remain blank.")
        )

    def retranslate(self)->None:
        self.setWindowTitle(tr("Advanced Compare")); self.title.setText(tr("Advanced Compare"))
        self.subtitle.setText(tr("Compare 2–4 players in a separate window. The existing Compare tab and main window remain unchanged."))
        self.season_label.setText(tr("Season")); self.add_button.setText(tr("+ Add Player"))
        self.core_group.setTitle(tr("A. Basic Comparison")); self.stat_group.setTitle(tr("B. Statcast Percentile Comparison"))
        self.footer_group.setTitle(tr("Data Range / Sources / Status"))
        for i,slot in enumerate(self.slots):
            slot.box.setTitle(tr(f"Player {chr(65+i)}")); slot.edit.setPlaceholderText(tr("Search player (e.g. Judge)"))
            if slot.bundle is None:slot.status.setText(tr("No player selected"))
        self._render()
