"""Change presentation receives only worker-produced summaries."""
from __future__ import annotations

from datetime import date
from PyQt6.QtCore import QDate, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QSpinBox, QDateEdit, QComboBox, QCheckBox, QPushButton, QLabel, QTableWidget, QGroupBox
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from config.i18n import tr
from services.freshness import source_ttl_days
from services.statcast_service import StatcastService


class PitchChangeView(QWidget):
    requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.payload = {}
        self.revision = 0
        self.state = 'idle'
        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)
        self.season = QSpinBox()
        self.season.setRange(2008, date.today().year)
        self.season.setValue(date.today().year)
        form.addRow(tr('Season'), self.season)
        self.cutoff = QDateEdit(QDate(date.today().year, 7, 1))
        self.cutoff.setCalendarPopup(True)
        self.cutoff.setDisplayFormat('yyyy-MM-dd')
        form.addRow(tr('Cutoff date'), self.cutoff)
        self.cadence = QComboBox()
        self.cadence.addItem(tr('Daily'), 'daily')
        self.cadence.addItem(tr('Weekly (Monday start)'), 'weekly')
        form.addRow(tr('Time interval'), self.cadence)
        self.pitch = QComboBox()
        form.addRow(tr('Pitch'), self.pitch)
        self.notice = QLabel()
        self.notice.setWordWrap(True)
        root.addWidget(self.notice)
        self.download = QCheckBox(tr('Allow one season query if raw cache is unavailable'))
        root.addWidget(self.download)
        self.load = QPushButton(tr('Analyze Change'))
        root.addWidget(self.load)
        self.status = QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.counts = QLabel()
        self.counts.setWordWrap(True)
        root.addWidget(self.counts)
        self.cards = {}
        for side, title in (('before', 'Before'), ('after', 'After')):
            box = QGroupBox(tr(title))
            label = QLabel()
            label.setWordWrap(True)
            QVBoxLayout(box).addWidget(label)
            root.addWidget(box)
            self.cards[side] = label
        self.difference = QLabel()
        self.difference.setWordWrap(True)
        root.addWidget(self.difference)
        self.table = QTableWidget()
        self.table.setMinimumHeight(190)
        root.addWidget(self.table)
        self.figure = Figure(figsize=(7, 5))
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(420)
        root.addWidget(self.canvas)
        self.samples = QTableWidget()
        self.samples.setMaximumHeight(220)
        root.addWidget(self.samples)
        self.help = QLabel()
        self.help.setWordWrap(True)
        root.addWidget(self.help)
        self.load.clicked.connect(self.requested.emit)
        self.season.valueChanged.connect(self.invalidate)
        self.cutoff.dateChanged.connect(self.invalidate)
        self.cadence.currentIndexChanged.connect(self.invalidate)
        self.pitch.currentIndexChanged.connect(self.refresh_presentation)
        self.invalidate()

    def key(self) -> tuple[int, str, str, int]:
        return (self.season.value(), self.cutoff.date().toString('yyyy-MM-dd'),
                self.cadence.currentData(), self.revision)

    def reset(self, season: int | None = None) -> None:
        if season is not None:
            self.season.setValue(season)
        self.download.setChecked(False)
        self.invalidate()

    def invalidate(self, *_args) -> None:
        self.revision += 1
        year = self.season.value()
        self.cutoff.blockSignals(True)
        self.cutoff.setDateRange(QDate(year, 1, 1), QDate(year, 12, 31))
        self.cutoff.blockSignals(False)
        self.payload = {}
        self.state = 'idle'
        self.load.setEnabled(True)
        self.refresh_presentation()

    def loading(self) -> None:
        self.state = 'loading'
        self.load.setEnabled(False)
        self.refresh_presentation()

    def failed(self) -> None:
        self.state = 'failed'
        self.load.setEnabled(True)
        self.refresh_presentation()

    def set_result(self, payload: dict) -> None:
        self.payload = payload
        self.state = payload['status']
        self.load.setEnabled(True)
        self.refresh_presentation()

    def refresh_presentation(self, *_args) -> None:
        from ui.pitch_analysis_view import PitchAnalysisView as Presentation
        from config.theme_tokens import chart_colors
        from matplotlib.dates import AutoDateLocator, ConciseDateFormatter
        year = self.season.value()
        start, end = StatcastService.season_dates(year)
        self.notice.setText(tr('Regular-season pitches only') + f' · {start} → {end}\n' +
            tr('Cache first. If permitted: estimated 1 request for this pitcher and season. Raw data stays in memory only (up to 2 entries); no permanent storage.') +
            f" TTL: {source_ttl_days(year, savant=True)*24:g} h.\n" +
            tr('Before: date < cutoff. After: date >= cutoff. Current season ends at today.'))
        states = {'idle':'Not loaded', 'loading':'Loading pitcher analysis…',
                  'failed':'Analysis failed; existing player data remains available.',
                  'cache_miss':'Raw cache unavailable. Check the query permission above and analyze again to fetch this season.',
                  'empty':'No data', 'unavailable':'Unverified',
                  'partial':'Partial success / interpret with caution', 'ready':'Ready'}
        self.status.setText(tr(states.get(self.state, 'Unverified')))
        self.help.setText(tr('Difference = after minus before. Median is the middle value; IQR is the central 50% width. Valid N < 30: interpret with caution. Missing and invalid values are not zero.')+'\n'+
            tr('IVB / HB unavailable: fields, units and direction have not been verified. No conversion or handedness flip is applied.')+'\n'+
            tr('Weekly points pool pitches Monday–Sunday, not daily averages. A week can cross the cutoff; before/after cards still split by exact date. Observed differences do not explain causes.'))
        rows = self.payload.get('pitches', [])
        Presentation.choices(self.pitch, [(r['pitch'], r['pitch']) for r in rows])
        r = next((r for r in rows if r['pitch'] == self.pitch.currentData()), None)
        p = self.payload
        self.counts.setText(f"Baseball Savant / pybaseball · {tr('Observed range')}: {p.get('observed_start') or '—'} → {p.get('observed_end') or '—'}\n"+
            tr('Raw / regular / classified / unclassified / excluded rows')+': '+
            ' / '.join(str(p.get(k,0)) for k in ('raw_rows','total','classified','unclassified','excluded_rows'))+
            (f"\n{r['pitch']} · {tr('Before')} N={r['before_n']} · {tr('After')} N={r['after_n']}" if r else ''))
        for side, label in self.cards.items():
            lines = []
            if r:
                lines.append(f"{tr('Pitches')}: {r[side+'_n']}")
                for field, metric in r['metrics'].items():
                    v = metric[side]
                    lines.append(f"{tr(field)} ({metric['unit']}): {tr('Median')} {Presentation.number(v['median'])} · IQR {Presentation.number(v['iqr'])} · N={v['n']} · {tr('Missing')}={v['missing']} · {tr('Excluded')}={v['excluded']}" +
                                 (' · '+tr('Interpret with caution') if v['small'] else ''))
            label.setText('\n'.join(lines) if lines else tr('No data'))
        self.difference.setText(' · '.join(f"{tr(field)}: {Presentation.number(metric['delta_median'])} {metric['unit']}" for field, metric in r['metrics'].items())+' ('+tr('After minus before')+')' if r else '')
        table_rows = []
        samples = []
        self.figure.clear()
        colors = chart_colors()
        self.figure.patch.set_facecolor(colors['figure'])
        for index, field in enumerate(('release_speed','release_spin_rate')):
            unit = 'mph' if index == 0 else 'rpm'
            metric = r['metrics'][field] if r else None
            ax = self.figure.add_subplot(2, 1, index+1)
            ax.set_facecolor(colors['axes'])
            ax.tick_params(colors=colors['text'])
            for spine in ax.spines.values():
                spine.set_color(colors['border'])
            ax.set_ylabel(unit, color=colors['text'])
            if metric:
                for side in ('before','after'):
                    v = metric[side]
                    table_rows.append([tr(field)+' ('+unit+')', tr('Before' if side=='before' else 'After'),
                        v['median'],v['iqr'],v['n'],v['missing'],v['excluded'],
                        tr('Interpret with caution' if v['small'] else 'Observed sample')])
                table_rows.append([tr(field)+' ('+unit+')', tr('After minus before'),metric['delta_median'],metric['delta_iqr'],'—','—','—','—'])
                points = metric['points']
                if points:
                    xs = [date.fromisoformat(v['date']) for v in points]
                    # NaN breaks the line for observed dates with no valid metric.
                    ax.plot(xs, [v['median'] if v['median'] is not None else float('nan') for v in points], marker='o', color=colors['primary'])
                    for x,v in zip(xs,points):
                        if v['median'] is not None:
                            ax.annotate(f"N={v['n']}",(x,v['median']),xytext=(0,5),textcoords='offset points',fontsize=7,color=colors['text'])
                        samples.append([tr(field),v['date'],v['median'],v['n'],v['missing'],v['excluded'],tr('Interpret with caution' if v['small'] else 'Observed sample')])
                cut = date.fromisoformat(p['cutoff'])
                ax.axvline(cut,color=colors['muted'],linestyle='--')
                ax.text(cut, .98, p['cutoff'],transform=ax.get_xaxis_transform(),va='top',color=colors['text'],fontsize=8)
                locator = AutoDateLocator(minticks=2,maxticks=5)
                ax.xaxis.set_major_locator(locator)
                ax.xaxis.set_major_formatter(ConciseDateFormatter(locator))
            else:
                ax.text(.5,.5,'—',transform=ax.transAxes,ha='center',color=colors['text'])
        for field in ('IVB','HB'):
            table_rows.append([field,tr('Unverified'),'—','—','—','—','—',tr('Unavailable')])
        Presentation.fill(self.table,['Metric','Period','Median','IQR','Valid N','Missing','Excluded','Sample'],table_rows,{})
        Presentation.fill(self.samples,['Metric','Date','Median','Valid N','Missing','Excluded','Sample'],samples,{})
        self.figure.subplots_adjust(left=.14,right=.96,top=.94,bottom=.09,hspace=.4)
        self.canvas.draw_idle()

# Dugout Atlas
# Copyright (c) 2026 dhtjr1236-eng
# Unauthorized redistribution or rebranding is prohibited.
