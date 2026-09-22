from __future__ import annotations

from typing import Literal

from PyQt6.QtCore import QEasingCurve, QSettings, Qt, QVariantAnimation
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QPushButton

ThemeName = Literal["light", "dark"]
THEME_STORAGE_KEY = "dugout-atlas-theme"

DARK_TOKENS = {
    "--color-bg": "#0B1220",
    "--color-surface": "#111827",
    "--color-surface-muted": "#0F172A",
    "--color-surface-selected": "#1C2B42",
    "--color-text": "#E5E7EB",
    "--color-text-muted": "#CBD5E1",
    "--color-text-subtle": "#94A3B8",
    "--color-border": "#263244",
    "--color-border-strong": "#334155",
    "--color-primary": "#3B82F6",
    "--color-primary-hover": "#60A5FA",
    "--color-primary-soft": "#1E3A5F",
    "--color-success": "#22C55E",
    "--color-warning": "#F59E0B",
    "--color-danger": "#EF4444",
    "--shadow-card": "0 2px 8px rgba(0, 0, 0, 0.24)",
}

LIGHT_TOKENS = {
    "--color-bg": "#F5F7FB",
    "--color-surface": "#FFFFFF",
    "--color-surface-muted": "#F8FAFC",
    "--color-surface-selected": "#EFF6FF",
    "--color-text": "#172033",
    "--color-text-muted": "#64748B",
    "--color-text-subtle": "#94A3B8",
    "--color-border": "#D9E1EC",
    "--color-border-strong": "#CBD5E1",
    "--color-primary": "#2563EB",
    "--color-primary-hover": "#1D4ED8",
    "--color-primary-soft": "#DBEAFE",
    "--color-success": "#16A34A",
    "--color-warning": "#D97706",
    "--color-danger": "#DC2626",
    "--shadow-card": "0 2px 8px rgba(15, 23, 42, 0.06)",
}


class ThemeManager:
    """Dugout Atlas의 PyQt6 전역 Light/Dark 테마를 관리한다."""

    def __init__(self, app: QApplication, template: str) -> None:
        self.app = app
        self.template = template
        self.settings = QSettings("Dugout Atlas", "Dugout Atlas")
        self.current_theme: ThemeName = self._initial_theme()
        self._animation: QVariantAnimation | None = None
        self._button: QPushButton | None = None

        self.apply(self.current_theme, animate=False)
        try:
            self.app.styleHints().colorSchemeChanged.connect(self._on_system_theme_changed)
        except Exception:
            pass

    def _stored_theme(self) -> ThemeName | None:
        raw = str(self.settings.value(THEME_STORAGE_KEY, "") or "").strip().lower()
        if raw in {"light", "dark"}:
            return raw  # type: ignore[return-value]
        if raw:
            self.settings.remove(THEME_STORAGE_KEY)
        return None

    def _system_theme(self) -> ThemeName:
        try:
            scheme = self.app.styleHints().colorScheme()
            if scheme == Qt.ColorScheme.Light:
                return "light"
            if scheme == Qt.ColorScheme.Dark:
                return "dark"
        except Exception:
            pass

        window_color = self.app.palette().window().color()
        return "dark" if window_color.lightness() < 128 else "light"

    def _initial_theme(self) -> ThemeName:
        return self._stored_theme() or self._system_theme()

    def attach_button(self, button: QPushButton) -> None:
        self._button = button
        button.clicked.connect(self.toggle)
        self._update_button()

    def toggle(self) -> None:
        target: ThemeName = "light" if self.current_theme == "dark" else "dark"
        self.settings.setValue(THEME_STORAGE_KEY, target)
        self.settings.sync()
        self.apply(target, animate=True)

    def apply(self, theme: ThemeName, *, animate: bool = True) -> None:
        old_theme = self.current_theme
        self.current_theme = theme

        if animate and not self._reduced_motion() and old_theme != theme:
            self._animate_theme(old_theme, theme)
        else:
            self.app.setStyleSheet(self._render(self._tokens(theme)))

        self._update_button()

    def _on_system_theme_changed(self, *_args: object) -> None:
        if self._stored_theme() is None:
            self.apply(self._system_theme(), animate=True)

    def _update_button(self) -> None:
        if self._button is None:
            return
        if self.current_theme == "dark":
            self._button.setText("Light")
            description = "Light Theme로 전환"
        else:
            self._button.setText("Dark")
            description = "Dark Theme로 전환"
        self._button.setToolTip(description)
        self._button.setAccessibleName(description)
        self._button.setAccessibleDescription("Dugout Atlas 화면 테마 전환 버튼")

    @staticmethod
    def _tokens(theme: ThemeName) -> dict[str, str]:
        return DARK_TOKENS if theme == "dark" else LIGHT_TOKENS

    def _render(self, tokens: dict[str, str]) -> str:
        rendered = self.template
        for key, value in tokens.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", value)
        return rendered

    def _reduced_motion(self) -> bool:
        hints = self.app.styleHints()
        for name in ("reduceMotion", "reducedMotion"):
            getter = getattr(hints, name, None)
            if callable(getter):
                try:
                    return bool(getter())
                except Exception:
                    pass
        return False

    def _animate_theme(self, source: ThemeName, target: ThemeName) -> None:
        start = self._tokens(source)
        end = self._tokens(target)

        animation = QVariantAnimation(self.app)
        animation.setDuration(180)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        def update(value: object) -> None:
            try:
                progress = float(value)
            except (TypeError, ValueError):
                progress = 1.0
            mixed: dict[str, str] = {}
            for key, target_value in end.items():
                source_value = start.get(key, target_value)
                if (
                    isinstance(source_value, str)
                    and isinstance(target_value, str)
                    and source_value.startswith("#")
                    and target_value.startswith("#")
                ):
                    mixed[key] = self._mix_color(source_value, target_value, progress)
                else:
                    mixed[key] = target_value if progress >= 0.5 else source_value
            self.app.setStyleSheet(self._render(mixed))

        animation.valueChanged.connect(update)
        animation.finished.connect(
            lambda: self.app.setStyleSheet(self._render(self._tokens(target)))
        )
        self._animation = animation
        animation.start()

    @staticmethod
    def _mix_color(start: str, end: str, progress: float) -> str:
        a = QColor(start)
        b = QColor(end)
        t = max(0.0, min(1.0, progress))

        def channel(x: int, y: int) -> int:
            return round(x + (y - x) * t)

        color = QColor(
            channel(a.red(), b.red()),
            channel(a.green(), b.green()),
            channel(a.blue(), b.blue()),
        )
        return color.name().upper()
