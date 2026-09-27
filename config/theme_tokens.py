from __future__ import annotations

from typing import Literal

ThemeName = Literal["light", "dark"]
AccentName = Literal["blue", "gold", "purple", "magenta", "emerald"]

DARK_TOKENS: dict[str, str] = {
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

LIGHT_TOKENS: dict[str, str] = {
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

ACCENT_OVERRIDES: dict[str, dict[str, dict[str, str]]] = {
    "blue": {
        "dark": {"--color-primary":"#3B82F6","--color-primary-hover":"#60A5FA","--color-primary-soft":"#1E3A5F","--color-surface-selected":"#1C2B42"},
        "light": {"--color-primary":"#2563EB","--color-primary-hover":"#1D4ED8","--color-primary-soft":"#DBEAFE","--color-surface-selected":"#EFF6FF"},
    },
    "gold": {
        "dark": {"--color-primary":"#D6B36A","--color-primary-hover":"#E6C985","--color-primary-soft":"#3A3020","--color-surface-selected":"#29251D"},
        "light": {"--color-primary":"#A97516","--color-primary-hover":"#8A5E0F","--color-primary-soft":"#FFF3D6","--color-surface-selected":"#FFF8E8"},
    },
    "purple": {
        "dark": {"--color-primary":"#9B7CF6","--color-primary-hover":"#B49AFB","--color-primary-soft":"#2B214D","--color-surface-selected":"#241E3C"},
        "light": {"--color-primary":"#6D4DD6","--color-primary-hover":"#5837BE","--color-primary-soft":"#EEE8FF","--color-surface-selected":"#F5F1FF"},
    },
    "magenta": {
        "dark": {"--color-primary":"#E65AAE","--color-primary-hover":"#F07BC0","--color-primary-soft":"#46223A","--color-surface-selected":"#352033"},
        "light": {"--color-primary":"#C02678","--color-primary-hover":"#A51D65","--color-primary-soft":"#FCE7F3","--color-surface-selected":"#FFF1F7"},
    },
    "emerald": {
        "dark": {"--color-primary":"#34D399","--color-primary-hover":"#6EE7B7","--color-primary-soft":"#163C34","--color-surface-selected":"#17342E"},
        "light": {"--color-primary":"#059669","--color-primary-hover":"#047857","--color-primary-soft":"#D1FAE5","--color-surface-selected":"#ECFDF5"},
    },
}

_active_theme: ThemeName = "dark"
_active_accent: AccentName = "blue"


def tokens_for(theme: ThemeName, accent: AccentName | str | None = None) -> dict[str, str]:
    base = dict(DARK_TOKENS if theme == "dark" else LIGHT_TOKENS)
    chosen = str(accent or _active_accent)
    if chosen not in ACCENT_OVERRIDES:
        chosen = "blue"
    base.update(ACCENT_OVERRIDES[chosen][theme])
    return base


def set_active_theme(theme: ThemeName) -> None:
    global _active_theme
    _active_theme = theme


def active_theme() -> ThemeName:
    return _active_theme


def set_active_accent(accent: AccentName | str) -> None:
    global _active_accent
    _active_accent = accent if accent in ACCENT_OVERRIDES else "blue"  # type: ignore[assignment]


def active_accent() -> AccentName:
    return _active_accent


def chart_colors() -> dict[str, str]:
    tokens = tokens_for(_active_theme)
    return {
        "figure": tokens["--color-surface"],
        "axes": tokens["--color-surface"],
        "text": tokens["--color-text"],
        "muted": tokens["--color-text-muted"],
        "border": tokens["--color-border-strong"],
        "primary": tokens["--color-primary"],
    }
