from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace

from PyQt6.QtCore import QDate, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QSlider, QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.offsetbox import AnnotationBbox

from config.i18n import tr
from services.player_name_localization import localized_player_name
from config.theme_tokens import chart_colors, active_theme
from services.season_race import (
    RacePlan, RacePlayer, RaceService, demo_points, drawdown, peak,
)
from workers.qt_worker import TaskThread
from ui.character_renderer import CharacterRenderer
from services.headshots import load_headshot

NOTICE = 'FanGraphs currently returned fWAR for regular-season start through the selected date; not a historical snapshot.'
LINK_NOTICE = 'Lines only connect samples. Markers and values represent successful FanGraphs range requests only.'
RANGE_NOTICE = 'Custom-range fielding components may use period-based processing; range WAR need not add up to final season WAR.'


class RaceThread(TaskThread):
    progress = pyqtSignal(object)


class SeasonRaceView(QWidget):
    def __init__(self, player_service, parent=None, *, demo_only=False):
        super().__init__(parent)
        self.service = RaceService(player_service.fangraphs)
        self._demo_only = demo_only
        self._demo_window = None
        self.players = []
        self.season = 2025
        self.axis = None
        self.points = [{}, {}]
        self.resolved = []
        self._workers = set()
        self._image_workers = set()
        self._image_requested = set()
        self.renderer = CharacterRenderer()
        self._confirmation = None
        self._cancel = None
        self._generation = 0
        self._seen = set()
        self._sparkles = set()
        self._demo = demo_only
        self.mode = 'Ready'
        self._progress_text = ''
        self._counts = None
        self._estimated_seconds = 0.0
        self._last_error = ''
        root = QVBoxLayout(self)
        self.heading = QLabel(); self.heading.setObjectName('title'); root.addWidget(self.heading)
        roles = QHBoxLayout()
        self.role_boxes = []
        self.role_labels = []
        for i in range(2):
            label = QLabel(chr(65+i)); roles.addWidget(label); self.role_labels.append(label)
            combo = QComboBox(); combo.addItem(tr('Batting'), 'bat'); combo.addItem(tr('Pitching'), 'pit')
            combo.currentIndexChanged.connect(self._role_changed)
            roles.addWidget(combo); self.role_boxes.append(combo)
        roles.addStretch(); root.addLayout(roles)
        actions = QHBoxLayout()
        self.granularity = QComboBox()
        for label, mode in [('Monthly', 'monthly'), ('Bi-Weekly', 'bi-weekly'),
                            ('Weekly', 'weekly'), ('Full detail', 'full')]:
            self.granularity.addItem(tr(label), mode)
        self.granularity.setCurrentIndex(2)
        self.preview = QPushButton()
        self.full = self.preview  # Compatibility alias; only one load action.
        self.cancel_button = QPushButton()
        self.demo_button = QPushButton(); self.save_button = QPushButton()
        for b in (self.granularity, self.preview, self.cancel_button, self.demo_button, self.save_button):
            actions.addWidget(b)
        root.addLayout(actions)
        filters = QHBoxLayout()
        self.range_enabled = QCheckBox(tr('Custom Range'))
        self.range_start = QDateEdit(QDate(2025, 3, 1))
        self.range_end = QDateEdit(QDate(2025, 10, 31))
        for edit in (self.range_start, self.range_end):
            edit.setDisplayFormat('MM-dd'); edit.setCalendarPopup(True)
            edit.setEnabled(False)
            self.range_enabled.toggled.connect(edit.setEnabled)
        self.marker_mode = QComboBox()
        self.marker_mode.addItem(tr('Vector helmet'), 'vector')
        self.marker_mode.addItem(tr('MLB headshot'), 'headshot')
        self.marker_mode.currentIndexChanged.connect(self._marker_changed)
        for widget in (self.range_enabled, self.range_start, self.range_end, self.marker_mode):
            filters.addWidget(widget)
        root.addLayout(filters)
        self.preview.clicked.connect(lambda: self.start(self.granularity.currentData()))
        self.cancel_button.clicked.connect(self.cancel)
        self.demo_button.clicked.connect(self.start_demo)
        self.save_button.clicked.connect(self.save_image)
        self.status = QLabel(); self.status.setWordWrap(True); root.addWidget(self.status)
        self.figure = Figure(figsize=(10, 4.5), layout='constrained')
        self.canvas = FigureCanvasQTAgg(self.figure); root.addWidget(self.canvas, 1)
        self._motion_cid = self.canvas.mpl_connect('motion_notify_event', self._hover)
        self._hover_targets = []
        self.values = QLabel(); self.values.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.values)
        self.slider = QSlider(Qt.Orientation.Horizontal); self.slider.setRange(0, 0)
        self.slider.valueChanged.connect(self._date_changed); root.addWidget(self.slider)
        controls = QHBoxLayout()
        self.play = QPushButton(); self.restart = QPushButton(); self.speed_label = QLabel()
        self.speed = QComboBox()
        for speed in (0.5, 1, 2, 4): self.speed.addItem(f'{speed}×', speed)
        self.speed.setCurrentIndex(1)
        self.effects = QCheckBox()
        for widget in (self.play, self.restart, self.speed_label, self.speed, self.effects): controls.addWidget(widget)
        controls.addStretch(); root.addLayout(controls)
        self.notice = QLabel(); self.notice.setWordWrap(True); root.addWidget(self.notice)
        self.timer = QTimer(self); self.timer.setInterval(700); self.timer.timeout.connect(self._advance)
        self.effect_timer = QTimer(self); self.effect_timer.setSingleShot(True); self.effect_timer.setInterval(650)
        self.effect_timer.timeout.connect(self._clear_effect)
        self.play.clicked.connect(self.toggle_play); self.restart.clicked.connect(self.reset)
        self.speed.currentIndexChanged.connect(lambda: self.timer.setInterval(round(700/self.speed.currentData())))
        self.effects.toggled.connect(self._effects_changed)
        self.retranslate()
        if demo_only:
            for widget in (self.preview, self.granularity, self.range_enabled, self.range_start, self.range_end, self.marker_mode, *self.role_boxes, *self.role_labels): widget.hide()
            self.setWindowTitle(tr('Fictional demo'))
        self._buttons()

    def set_players(self, bundles, season):
        self.cancel()
        self.players = [RacePlayer(p.profile.id, p.profile.full_name,
                                  'pit' if p.profile.is_pitcher else 'bat') for p in bundles[:2]]
        self.season = season
        for edit in (self.range_start, self.range_end):
            old = edit.date()
            edit.setDateRange(QDate(season, 1, 1), QDate(season, 12, 31))
            edit.setDate(QDate(season, old.month(), min(old.day(), QDate(season, old.month(), 1).daysInMonth())))
        self.axis = None; self.points = [{}, {}]; self.resolved = []; self._demo = False
        self._seen.clear(); self._sparkles.clear(); self._last_error = ''; self._progress_text = ''; self._counts = None
        for i, box in enumerate(self.role_boxes):
            box.blockSignals(True)
            box.setCurrentIndex(1 if i < len(self.players) and self.players[i].role == 'pit' else 0)
            box.blockSignals(False)
        self.mode = 'Ready'; self._buttons(); self._marker_changed()

    def _role_changed(self):
        self.cancel(); self.axis = None; self.points = [{}, {}]; self.resolved = []
        self._demo = False; self._seen.clear(); self._sparkles.clear(); self._progress_text = ''; self._counts = None
        self.mode = 'Ready'; self._buttons(); self._draw()

    def _buttons(self):
        busy = bool(self._workers or self._confirmation)
        enabled = len(self.players) == 2 and not busy
        self.preview.setEnabled(enabled); self.full.setEnabled(enabled)
        self.demo_button.setEnabled(not busy); self.cancel_button.setEnabled(busy)
        self.play.setEnabled(bool(self.axis and self.axis.dates) and not busy)
        self.save_button.setEnabled(bool(self.axis))
        for box in (*self.role_boxes, self.granularity, self.range_enabled): box.setEnabled(not busy)
        for edit in (self.range_start, self.range_end):
            edit.setEnabled(not busy and self.range_enabled.isChecked())

    def _launch(self, task, on_success):
        self.cancel()
        generation = self._generation
        event = threading.Event(); self._cancel = event
        thread = RaceThread(lambda: task(event, thread.progress.emit), self)
        self._workers.add(thread)
        def progress(message):
            if generation == self._generation: self._progress(message)
        def success(result):
            if generation == self._generation: on_success(result)
        def failure(message):
            if generation == self._generation:
                self.mode = 'Cancelled' if event.is_set() else 'Failed'
                self._last_error = message.splitlines()[-1].split(': ', 1)[-1] if message else ''
                self._draw()
        def finished():
            self._workers.discard(thread); thread.deleteLater(); self._buttons()
        thread.progress.connect(progress); thread.succeeded.connect(success); thread.failed.connect(failure)
        thread.finished.connect(finished)
        thread.start(); self._buttons()

    def start(self, preview: bool | str = True) -> None:
        if len(self.players) != 2 or self._workers or self._confirmation:
            return
        mode = ('weekly' if preview else 'full') if isinstance(preview, bool) else preview
        start = self.range_start.date().toString('yyyy-MM-dd') if self.range_enabled.isChecked() else None
        end = self.range_end.date().toString('yyyy-MM-dd') if self.range_enabled.isChecked() else None
        if start and end and start > end:
            self._last_error = 'Start date must precede end date.'; self._draw(); return
        self._demo = False; self.axis = None; self.points = [{}, {}]; self.resolved = []
        self._seen.clear(); self._sparkles.clear(); self._last_error = ''; self._progress_text = ''; self._counts = None
        players = [RacePlayer(p.mlbam_id, p.name, b.currentData()) for p, b in zip(self.players, self.role_boxes)]
        season = self.season
        self._launch(lambda cancel, emit: self.service.prepare(players, season, mode, cancel, start, end),
                     lambda plan: self._prepared(plan, mode))
        self.mode = 'Preparing request estimate…'; self._draw()

    def _prepared(self, plan: RacePlan, mode: str) -> None:
        """Keep the Qt event loop running while the user reviews a large request."""
        self._progress(plan.message())
        generation = self._generation
        def run():
            if generation != self._generation:
                return
            self._launch(lambda cancel, emit: self.service.execute(plan, cancel, emit),
                         lambda _axis: self._loaded({'full': 'Full detail', 'weekly': 'Weekly',
                                                    'monthly': 'Monthly', 'bi-weekly': 'Bi-Weekly'}[mode]))
            self.mode = 'Loading…'; self._draw()
        if mode == 'full' and plan.new_jobs > 50:
            dialog = QMessageBox(self)
            dialog.setWindowTitle(tr('Full detail'))
            dialog.setText(tr('Requests: {total}; cache hits: {hits}; new: {new}. Minimum estimated wait: {seconds} seconds. Network time is additional. Continue?').format(
                total=plan.total_jobs, hits=plan.cache_hits, new=plan.new_jobs,
                seconds=round(plan.estimated_seconds, 1)))
            dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            dialog.setDefaultButton(QMessageBox.StandardButton.No)
            self._confirmation = dialog
            def decided(result):
                self._confirmation = None
                dialog.deleteLater()
                if result == QMessageBox.StandardButton.Yes:
                    QTimer.singleShot(0, run)
                else:
                    self.mode = 'Cancelled'; self._draw()
                self._buttons()
            dialog.finished.connect(decided)
            self.mode = 'Awaiting confirmation'; self._draw()
            dialog.open()
        else:
            QTimer.singleShot(0, run)

    def _marker_changed(self) -> None:
        """Download each chosen ID once per view, with immediate vector placeholders."""
        if self.marker_mode.currentData() == 'headshot' and not self._demo:
            for player in self.players:
                pid = player.mlbam_id
                if pid in self._image_requested:
                    continue
                self._image_requested.add(pid)
                worker = TaskThread(lambda pid=pid: load_headshot(pid), self)
                self._image_workers.add(worker)
                def loaded(rgba, pid=pid):
                    if rgba is not None:
                        self.renderer.set_headshot(pid, rgba)
                        self._draw()
                def finished(worker=worker):
                    self._image_workers.discard(worker); worker.deleteLater()
                worker.succeeded.connect(loaded)
                worker.finished.connect(finished)
                worker.start()
        self._draw()

    def _loaded(self, mode):
        self.mode = mode
        self.slider.setValue(0); self._draw()

    def _progress(self, message):
        if message['kind'] == 'plan':
            self.axis = message['axis']; self.resolved = message['players']
            self.slider.setRange(0, max(0, len(self.axis.dates)-1))
            self._counts = [message['total'], message['hits'], 0, message['new']]
            self._estimated_seconds = message.get('estimated_seconds', 0)
        else:
            for i, player in enumerate(self.resolved):
                if player == message['player'] and message['point'] is not None:
                    self.points[i][message['day']] = message['point']
            if self._counts: self._counts[2] = message['done']
        self._draw()

    def cancel(self):
        self._generation += 1
        if self._confirmation is not None:
            self._confirmation.reject()
        if self._cancel: self._cancel.set()
        self.timer.stop(); self.effect_timer.stop(); self._sparkles.clear()
        if self._workers: self.mode = 'Cancelled'
        if hasattr(self, 'status'): self._draw()

    def start_demo(self):
        if not self._demo_only:
            if self._demo_window is None:
                self._demo_window = SeasonRaceView(SimpleNamespace(fangraphs=self.service.fg), self, demo_only=True)
                self._demo_window.setWindowFlag(Qt.WindowType.Window, True)
                self._demo_window.resize(1200, 850)
            self._demo_window.season = self.season
            self._demo_window.show()
            self._demo_window.start_demo()
            return
        if self._workers: return
        self.axis = None; self.points = [{}, {}]; self.resolved = []; self._seen.clear()
        self._last_error = ''; self._progress_text = ''; self._counts = None; self._demo = True
        # No FanGraphs requests or real cache writes in demo mode.
        def work(cancel, emit):
            axis = self.service.schedule(self.season, cancel)
            return axis, demo_points(axis)
        def done(result):
            self.axis, self.points = result
            self.slider.setRange(0, len(self.axis.dates)-1); self.slider.setValue(0)
            self.mode = 'Fictional demo'; self._draw()
        self._launch(work, done); self.mode = 'Loading…'; self._draw()

    def toggle_play(self):
        if self.timer.isActive(): self.timer.stop()
        elif self.axis and self.axis.dates:
            if self.slider.value() == self.slider.maximum(): self.reset()
            self.timer.start()
        self.play.setText(tr('Pause' if self.timer.isActive() else 'Play'))

    def reset(self):
        self.timer.stop(); self.effect_timer.stop(); self._seen.clear(); self._sparkles.clear()
        self.slider.setValue(0); self._date_changed(0)
        self.play.setText(tr('Play'))

    def _advance(self):
        if self.slider.value() >= self.slider.maximum():
            self.timer.stop(); self.play.setText(tr('Play')); return
        self.slider.setValue(self.slider.value()+1)
        if self.slider.value() == self.slider.maximum():
            self.timer.stop(); self.play.setText(tr('Play'))

    def _date_changed(self, _value):
        self._sparkles.clear()
        if self.axis and self.axis.dates:
            day = self.axis.dates[self.slider.value()]
            for i, points in enumerate(self.points):
                p = peak(points)
                if p and p.day == day and i not in self._seen:
                    self._seen.add(i)
                    if not self.effects.isChecked(): self._sparkles.add(i)
            if self._sparkles: self.effect_timer.start()
        self._draw()

    def _effects_changed(self):
        self.effect_timer.stop(); self._sparkles.clear(); self._draw()

    def _clear_effect(self):
        self._sparkles.clear(); self._draw()

    def _draw(self):
        if self._counts:
            total, hits, done, new = self._counts
            self._progress_text = f"{tr('Requests')}: {total} · {tr('Cache hits')}: {hits} · {done} / {new} · {tr('Minimum wait (seconds)')}: {self._estimated_seconds:g}"
        colors = chart_colors()
        self.figure.clear(); ax = self.figure.add_subplot(111)
        self.figure.set_facecolor(colors['figure']); ax.set_facecolor(colors['axes'])
        ax.tick_params(colors=colors['text']); ax.yaxis.label.set_color(colors['text'])
        for spine in ax.spines.values(): spine.set_color(colors['border'])
        ax.grid(alpha=.18, color=colors['muted']); ax.set_ylabel('fWAR')
        self._hover_targets = []
        names = [localized_player_name(p.mlbam_id, p.name) for p in self.players] if not self._demo else ['Demo A', 'Demo B']
        self.heading.setText(f"{tr('Season Race')} · {self.season} · " + ' / '.join(names))
        self.status.setText(f"{tr('Fictional demo') if self._demo else 'Source: FanGraphs · Metric: fWAR'} · {tr(self.mode)}\n{self._progress_text}" + (f'\n{tr(self._last_error)}' if self._last_error else ''))
        self.values.setText(tr('Select two players; the race uses slots A and B.'))
        if self.axis and self.axis.dates:
            index = min(self.slider.value(), len(self.axis.dates)-1)
            day = self.axis.dates[index]; date_index = {d:i for i,d in enumerate(self.axis.dates)}
            values = [day]; stamps = []
            palette = [colors['primary'], ('#F59E0B' if active_theme() == 'dark' else '#B45309') if colors['primary'] not in ('#D6B36A','#A97516') else ('#9B7CF6' if active_theme() == 'dark' else '#6D4DD6')]
            for i, points in enumerate(self.points):
                name = names[i] if i < len(names) else chr(65+i)
                valid = sorted((p for p in points.values() if p.day in date_index), key=lambda p:p.day)
                xs = [date_index[p.day] for p in valid]; ys = [p.war for p in valid]
                ax.plot(xs, ys, linestyle='--', color=palette[i], alpha=.35, linewidth=1)
                previous = [p for p in valid if p.day <= day]
                if previous:
                    ax.plot([date_index[p.day] for p in previous], [p.war for p in previous],
                            color=palette[i], marker='o' if i == 0 else 's', markersize=3, label=name)
                    # Holding the last real marker is a visual connection only.
                    last = previous[-1]; x = date_index[last.day]
                    ax.add_artist(AnnotationBbox(self.renderer.marker(self.players[i].mlbam_id if not self._demo and i < len(self.players) else -(i+1), name, palette[i], self.marker_mode.currentData()), (x,last.war), frameon=False))
                    if i in self._sparkles and not self.effects.isChecked():
                        ax.scatter([x], [last.war], marker='*', s=1900, color='#FFD166', alpha=.4, zorder=2)
                    if drawdown(points, day) and not self.effects.isChecked():
                        ax.scatter([index], [points[day].war], s=2300, color=colors['muted'], alpha=.15, zorder=1)
                current = points.get(day)
                values.append(f'{chr(65+i)}: {repr(current.war) if current else tr("No sampled point")}')
                highest = peak(points)
                if highest:
                    ax.annotate(f'{chr(65+i)} {tr("Peak")}: {highest.war:.3f} ({highest.day})',
                                (date_index[highest.day], highest.war),
                                xytext=((-6 if date_index[highest.day] > len(self.axis.dates)*.7 else 6),18+i*16),
                                ha='right' if date_index[highest.day] > len(self.axis.dates)*.7 else 'left',
                                textcoords='offset points', color=palette[i], fontsize=8)
                for p in valid:
                    self._hover_targets.append((date_index[p.day],p.war,f'{name} · {p.day} · fWAR {repr(p.war)}'))
                    stamps.append(p.fetched_at)
            ax.axvline(index,color=colors['muted'],alpha=.35)
            ax.set_xlim(-2,max(2,len(self.axis.dates)+1))
            ticks = sorted({round(i*(len(self.axis.dates)-1)/5) for i in range(6)})
            ax.set_xticks(ticks, [self.axis.dates[t][5:] for t in ticks])
            ax.margins(y=.3)
            handles, labels = ax.get_legend_handles_labels()
            if handles:
                legend = ax.legend(facecolor=colors['axes'], edgecolor=colors['border'])
                for text in legend.get_texts(): text.set_color(colors['text'])
            self.values.setText('   |   '.join(values))
            self.status.setText(self.status.text()+f"\n{tr('Cache updated')}: {max(stamps) if stamps else '—'} · {tr('Samples')}: {len(self.points[0])} / {len(self.points[1])}")
        self.canvas.draw_idle()

    def _hover(self, event):
        if event.x is None or event.y is None or not event.inaxes:
            self.canvas.setToolTip(''); return
        best = None
        for x,y,text in self._hover_targets:
            px,py = event.inaxes.transData.transform((x,y))
            distance = (px-event.x)**2 + (py-event.y)**2
            if distance < 100 and (best is None or distance < best[0]): best = distance,text
        self.canvas.setToolTip(best[1] if best else '')

    def save_image(self, path=None):
        if not self.axis: return False
        if not isinstance(path, (str, Path)):
            path, _ = QFileDialog.getSaveFileName(self, tr('Save current still'), 'season-race.png', 'PNG (*.png);;JPEG (*.jpg *.jpeg)')
        if not path: return False
        suffix = Path(path).suffix.lower()
        if suffix not in {'.png','.jpg','.jpeg'}:
            QMessageBox.warning(self, tr('Save'), tr('Choose PNG or JPEG.')); return False
        self.canvas.draw()
        ok = self.grab().save(str(path), 'PNG' if suffix == '.png' else 'JPEG', 95)
        if not ok: QMessageBox.warning(self, tr('Save'), tr('Image save failed.'))
        return ok

    def retranslate(self):
        for button, label in ((self.preview,'Load samples'),(self.cancel_button,'Cancel'),
                              (self.demo_button,'Fictional demo'),(self.save_button,'Save current still'),
                              (self.restart,'Restart')): button.setText(tr(label))
        self.play.setText(tr('Pause' if self.timer.isActive() else 'Play'))
        for i, label in enumerate(('Monthly', 'Bi-Weekly', 'Weekly', 'Full detail')):
            self.granularity.setItemText(i, tr(label))
        self.range_enabled.setText(tr('Custom Range'))
        self.marker_mode.setItemText(0, tr('Vector helmet'))
        self.marker_mode.setItemText(1, tr('MLB headshot'))
        self.speed_label.setText(tr('Speed')); self.effects.setText(tr('Animation OFF'))
        for box in self.role_boxes:
            box.setItemText(0,tr('Batting')); box.setItemText(1,tr('Pitching'))
        self.notice.setText(tr('Fictional values for UI demonstration only. No real player records or FanGraphs cache writes.') if self._demo_only else '\n'.join(tr(t) for t in (NOTICE, LINK_NOTICE, RANGE_NOTICE)))
        self._draw()

    def hideEvent(self, event):
        self.cancel()
        if self._motion_cid is not None:
            self.canvas.mpl_disconnect(self._motion_cid); self._motion_cid = None
        if self._demo_window is not None: self._demo_window.close()
        super().hideEvent(event)

    def showEvent(self, event):
        if self._motion_cid is None:
            self._motion_cid = self.canvas.mpl_connect('motion_notify_event', self._hover)
        self.retranslate(); super().showEvent(event)

    def closeEvent(self, event):
        self.cancel()
        if self._motion_cid is not None:
            self.canvas.mpl_disconnect(self._motion_cid); self._motion_cid = None
        super().closeEvent(event)
