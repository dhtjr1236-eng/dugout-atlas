import pytest
from PyQt6.QtCore import QEvent, QPoint, QPointF, QSettings, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton, QScrollArea, QTabWidget, QWidget
from config import preferences
from ui.motion import MotionManager


@pytest.fixture
def motion(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path/'motion.ini'), QSettings.Format.IniFormat)
    monkeypatch.setattr(preferences, 'store', lambda: settings)
    manager = MotionManager(app)
    yield app, manager
    app.removeEventFilter(manager)
    manager.deleteLater()
    app.processEvents()


def test_button_does_not_delay_or_duplicate_clicks(motion):
    app, manager = motion
    button = QPushButton('Run')
    button.show()
    app.processEvents()
    clicked = []
    button.clicked.connect(lambda: clicked.append(1))
    try:
        for _ in range(3):
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        assert len(clicked) == 3
        overlay = button._button_feedback
        assert overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        overlay.animation.setCurrentTime(overlay.animation.duration())
        button.setEnabled(False)
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        assert len(clicked) == 3 and overlay.level == 0
        assert overlay.animation.state() != overlay.animation.State.Running
    finally:
        button.close()
        button.deleteLater()


def test_tab_indicator_and_reduced_motion(motion):
    app, manager = motion
    tabs = QTabWidget()
    tabs.addTab(QWidget(), 'A')
    tabs.addTab(QWidget(), 'B')
    tabs.show()
    app.processEvents()
    try:
        tabs.setCurrentIndex(1)
        indicator = tabs.tabBar()._tab_indicator
        indicator.animation.setCurrentTime(indicator.animation.duration())
        assert indicator.position == tabs.tabBar().tabRect(1)
        preferences.save_preferences({'reduce_motion': True})
        manager.refresh_preferences()
        tabs.setCurrentIndex(0)
        assert indicator.position == tabs.tabBar().tabRect(0)
        assert indicator.animation.state() != indicator.animation.State.Running
    finally:
        tabs.close()
        tabs.deleteLater()


def test_discrete_wheel_smoothly_moves_scroll_without_changing_range(motion):
    app, manager = motion
    area = QScrollArea()
    content = QWidget()
    content.resize(300, 1600)
    area.setWidget(content)
    area.resize(400, 300)
    area.show()
    app.processEvents()
    try:
        before = area.verticalScrollBar().maximum()
        event = QWheelEvent(QPointF(20,20), QPointF(20,20), QPoint(), QPoint(0,-120),
                            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                            Qt.ScrollPhase.NoScrollPhase, False)
        app.sendEvent(area.viewport(), event)
        animation = area._smooth_scroll
        animation.setCurrentTime(animation.duration())
        assert area.verticalScrollBar().value() > 0
        assert area.verticalScrollBar().maximum() == before
    finally:
        area.close()
        area.deleteLater()
