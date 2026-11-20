"""Short, interruptible UI feedback. Never delays or synthesizes input actions."""
from PyQt6.QtCore import QEvent, QEasingCurve, QPropertyAnimation, QRectF, Qt, QVariantAnimation
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QPushButton, QToolButton, QScrollArea, QTabBar, QTabWidget, QWidget
from config.preferences import read_preferences
from config.theme_tokens import active_theme, tokens_for


class _Overlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setStyleSheet('background: transparent; border: none;')
        self.setGeometry(parent.rect())
        self.hide()


class ButtonFeedback(_Overlay):
    def __init__(self, button):
        super().__init__(button)
        self.setObjectName('_motion_button_feedback')
        self.level = 0.
        self.animation = QVariantAnimation(self)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self._frame)

    def _frame(self, value):
        self.level = float(value)
        self.setVisible(self.level > .001)
        self.raise_()
        self.update()

    def target(self, value, duration, animate=True):
        self.animation.stop()
        if not animate:
            self._frame(value)
            return
        self.animation.setDuration(duration)
        self.animation.setStartValue(self.level)
        self.animation.setEndValue(value)
        self.animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(tokens_for(active_theme())['--color-primary'])
        color.setAlpha(round(32 * self.level))
        painter.setBrush(color)
        color.setAlpha(round(150 * min(1., self.level)))
        painter.setPen(QPen(color, 1.2))
        inset = 1 + min(1., self.level) * .7
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(inset,inset,-inset,-inset), 6, 6)


class TabIndicator(_Overlay):
    def __init__(self, bar, manager):
        super().__init__(bar)
        self.setObjectName('_motion_tab_indicator')
        self.manager = manager
        self.position = QRectF(bar.tabRect(bar.currentIndex()))
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(190)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self._frame)
        bar.currentChanged.connect(self.move_to_selection)
        self.show()

    def _frame(self, value):
        self.position = QRectF(value)
        self.update()

    def move_to_selection(self, index):
        self.animation.stop()
        target = QRectF(self.parentWidget().tabRect(index))
        if self.manager.reduced_motion():
            self._frame(target)
            return
        self.animation.setStartValue(self.position)
        self.animation.setEndValue(target)
        self.animation.start()
        self.show()
        self.raise_()

    def paintEvent(self, event):
        if self.parentWidget().currentIndex() < 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tokens_for(active_theme())['--color-primary']))
        rect = self.position
        painter.drawRoundedRect(QRectF(rect.left()+5,rect.bottom()-2, max(0.,rect.width()-10),2), 1, 1)


class MotionManager(QObject):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self._reduced = read_preferences()['reduce_motion']
        app.installEventFilter(self)

    def reduced_motion(self):
        if self._reduced:
            return True
        hints = self.app.styleHints()
        for name in ('reduceMotion', 'reducedMotion'):
            getter = getattr(hints, name, None)
            if callable(getter) and getter():
                return True
        return False

    def refresh_preferences(self):
        self._reduced = read_preferences()['reduce_motion']
        if self.reduced_motion():
            for widget in self.app.allWidgets():
                if isinstance(widget, ButtonFeedback):
                    widget.animation.stop()
                    widget._frame(0.)
                elif isinstance(widget, TabIndicator):
                    widget.move_to_selection(widget.parentWidget().currentIndex())
                animation = getattr(widget, '_smooth_scroll', None)
                if animation is not None:
                    animation.stop()

    def eventFilter(self, widget, event):
        kind = event.type()
        if isinstance(widget, (QPushButton, QToolButton)):
            relevant = (QEvent.Type.Enter,QEvent.Type.Leave,QEvent.Type.MouseButtonPress,
                        QEvent.Type.MouseButtonRelease,QEvent.Type.KeyPress,QEvent.Type.KeyRelease,
                        QEvent.Type.Hide,QEvent.Type.EnabledChange,QEvent.Type.FocusOut,QEvent.Type.Resize)
            if kind not in relevant:
                return False
            overlay = widget.findChild(ButtonFeedback, '_motion_button_feedback')
            if kind in (QEvent.Type.Hide,QEvent.Type.EnabledChange,QEvent.Type.FocusOut):
                if overlay is not None:
                    overlay.target(0, 0, False)
                return False
            if not widget.isEnabled():
                return False
            if kind == QEvent.Type.Resize:
                if overlay is not None:
                    overlay.setGeometry(widget.rect())
                return False
            if kind in (QEvent.Type.MouseButtonPress,QEvent.Type.MouseButtonRelease) and event.button() != Qt.MouseButton.LeftButton:
                return False
            if kind in (QEvent.Type.KeyPress,QEvent.Type.KeyRelease):
                if event.key() not in (Qt.Key.Key_Space,Qt.Key.Key_Return,Qt.Key.Key_Enter) or event.isAutoRepeat():
                    return False
            if overlay is None:
                overlay = ButtonFeedback(widget)
                widget._button_feedback = overlay
            pressed = kind in (QEvent.Type.MouseButtonPress,QEvent.Type.KeyPress)
            target = 1. if pressed else .35 if kind == QEvent.Type.Enter or (kind in (QEvent.Type.MouseButtonRelease,QEvent.Type.KeyRelease) and widget.underMouse()) else 0.
            overlay.target(target, 80 if pressed else 160, not self.reduced_motion())
        elif isinstance(widget, QTabWidget) and kind == QEvent.Type.Show:
            bar = widget.tabBar()
            widget._motion_bar = bar
            overlay = bar.findChild(TabIndicator, '_motion_tab_indicator')
            if overlay is None:
                overlay = TabIndicator(bar, self)
            bar._tab_indicator = overlay
            overlay.setGeometry(bar.rect())
            overlay.show()
            overlay.raise_()
        elif isinstance(widget, QTabBar) and kind in (QEvent.Type.Show,QEvent.Type.Resize):
            overlay = widget.findChild(TabIndicator, '_motion_tab_indicator')
            if overlay is None:
                overlay = TabIndicator(widget, self)
                widget._tab_indicator = overlay
            overlay.setGeometry(widget.rect())
            overlay.animation.stop()
            overlay._frame(QRectF(widget.tabRect(widget.currentIndex())))
            overlay.show()
            overlay.raise_()
        elif (isinstance(widget, QWidget) and kind == QEvent.Type.Wheel and
              isinstance(widget.parentWidget(), QScrollArea)):
            area = widget.parentWidget()
            if (widget is not area.viewport() or self.reduced_motion() or
                not event.pixelDelta().isNull() or event.modifiers() != Qt.KeyboardModifier.NoModifier or
                not event.angleDelta().y()):
                return False
            bar = area.verticalScrollBar()
            if bar.maximum() <= bar.minimum():
                return False
            animation = getattr(area, '_smooth_scroll', None)
            if animation is None:
                animation = QPropertyAnimation(bar, b'value', area)
                animation.setDuration(170)
                animation.setEasingCurve(QEasingCurve.Type.OutCubic)
                area._smooth_scroll = animation
            current = bar.value()
            target = animation.endValue() if animation.state() == animation.State.Running else current
            animation.stop()
            target = max(bar.minimum(), min(bar.maximum(), round(target - event.angleDelta().y()/120 * bar.singleStep()*3)))
            animation.setStartValue(current)
            animation.setEndValue(target)
            animation.start()
            event.accept()
            return True
        return False
