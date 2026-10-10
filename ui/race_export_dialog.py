"""Small nonblocking export options dialog."""
from __future__ import annotations
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QComboBox, QSpinBox, QCheckBox, QLabel
from PIL import features
from config.i18n import tr
from services.race_animation import AnimationOptions


class RaceExportDialog(QDialog):
    def __init__(self, dates: tuple[str, ...], parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr('Save animation'))
        layout=QFormLayout(self)
        self.start=QComboBox(); self.end=QComboBox()
        self.start.addItems(dates); self.end.addItems(dates); self.end.setCurrentIndex(len(dates)-1)
        self.start.currentIndexChanged.connect(lambda i: self.end.setCurrentIndex(max(i,self.end.currentIndex())))
        self.end.currentIndexChanged.connect(lambda i: self.start.setCurrentIndex(min(i,self.start.currentIndex())))
        self.format=QComboBox(); self.format.addItem('GIF')
        if features.check('webp'): self.format.addItem('WEBP')
        self.seconds=QSpinBox(); self.seconds.setRange(6,12); self.seconds.setValue(8)
        self.fps=QComboBox(); self.fps.addItems(['5','10']); self.fps.setCurrentIndex(1)
        self.width=QComboBox(); self.width.addItem('640 × 360',640); self.width.addItem('960 × 540',960); self.width.setCurrentIndex(1)
        self.loop=QCheckBox(tr('Repeat animation')); self.loop.setChecked(True)
        for label,widget in [('Start date',self.start),('End date',self.end),('Format',self.format),('Duration (seconds)',self.seconds),('Frames per second',self.fps),('Resolution',self.width)]:
            layout.addRow(tr(label),widget)
        layout.addRow(self.loop)
        note=QLabel(tr('Exports loaded samples with a fixed axis. No extra API requests.'))
        note.setWordWrap(True); layout.addRow(note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addRow(buttons)

    def options(self) -> AnimationOptions:
        return AnimationOptions(self.format.currentText(),self.seconds.value(),int(self.fps.currentText()),self.width.currentData(),self.loop.isChecked())
