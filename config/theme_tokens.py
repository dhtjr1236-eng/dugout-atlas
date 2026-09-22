from __future__ import annotations

from typing import Literal

ThemeName = Literal["light", "dark"]

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

_active_theme: ThemeName = "dark"


def tokens_for(theme: ThemeName) -> dict[str, str]:
    return DARK_TOKENS if theme == "dark" else LIGHT_TOKENS


def set_active_theme(theme: ThemeName) -> None:
    global _active_theme
    _active_theme = theme


def active_theme() -> ThemeName:
    return _active_theme


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
