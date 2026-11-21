from __future__ import annotations

from typing import Literal

ThemeName = Literal["light", "dark"]
AccentName = Literal[
    "blue",
    "gold",
    "purple",
    "magenta",
    "emerald",
    "neon",
]

DARK_TOKENS: dict[str, str] = {
    "--color-bg": "#0B1120",
    "--color-surface": "#162032",
    "--color-surface-muted": "#0F172A",
    "--color-surface-selected": "#1C2B42",
    "--color-text": "#F8FAFC",
    "--color-text-muted": "#CBD5E1",
    "--color-text-subtle": "#94A3B8",
    "--color-border": "#1E293B",
    "--color-border-strong": "#334155",
    "--color-primary": "#38BDF8",
    "--color-primary-hover": "#7DD3FC",
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
        "dark": {
            "--color-primary": "#38BDF8",
            "--color-primary-hover": "#7DD3FC",
            "--color-primary-soft": "#0C4A6E",
            "--color-surface-selected": "#1C2B42",
        },
        "light": {
            "--color-primary": "#2563EB",
            "--color-primary-hover": "#1D4ED8",
            "--color-primary-soft": "#DBEAFE",
            "--color-surface-selected": "#EFF6FF",
        },
    },

    "gold": {
        "dark": {
            "--color-primary": "#D6B36A",
            "--color-primary-hover": "#E6C985",
            "--color-primary-soft": "#3A3020",
            "--color-surface-selected": "#29251D",
        },
        "light": {
            "--color-primary": "#A97516",
            "--color-primary-hover": "#8A5E0F",
            "--color-primary-soft": "#FFF3D6",
            "--color-surface-selected": "#FFF8E8",
        },
    },

    "purple": {
        "dark": {
            "--color-primary": "#9B7CF6",
            "--color-primary-hover": "#B49AFB",
            "--color-primary-soft": "#2B214D",
            "--color-surface-selected": "#241E3C",
        },
        "light": {
            "--color-primary": "#6D4DD6",
            "--color-primary-hover": "#5837BE",
            "--color-primary-soft": "#EEE8FF",
            "--color-surface-selected": "#F5F1FF",
        },
    },

    "magenta": {
        "dark": {
            "--color-primary": "#E65AAE",
            "--color-primary-hover": "#F07BC0",
            "--color-primary-soft": "#46223A",
            "--color-surface-selected": "#352033",
        },
        "light": {
            "--color-primary": "#C02678",
            "--color-primary-hover": "#A51D65",
            "--color-primary-soft": "#FCE7F3",
            "--color-surface-selected": "#FFF1F7",
        },
    },

    "emerald": {
        "dark": {
            "--color-primary": "#34D399",
            "--color-primary-hover": "#6EE7B7",
            "--color-primary-soft": "#163C34",
            "--color-surface-selected": "#17342E",
        },
        "light": {
            "--color-primary": "#059669",
            "--color-primary-hover": "#047857",
            "--color-primary-soft": "#D1FAE5",
            "--color-surface-selected": "#ECFDF5",
        },
    },

    "neon": {
        "dark": {
            "--color-bg": "#050D16",
            "--color-surface": "#0A1622",
            "--color-surface-muted": "#071120",
            "--color-surface-selected": "#12293A",
            "--color-border": "#123040",
            "--color-border-strong": "#1E4A5F",
            "--color-primary": "#00E5FF",
            "--color-primary-hover": "#7FFAFF",
            "--color-primary-soft": "#0A2E3F",
        },
        "light": {
            "--color-text-subtle": "#52657A",
            "--color-text-muted": "#52657A",
            "--color-primary": "#0E7490",
            "--color-primary-hover": "#155E75",
            "--color-primary-soft": "#CFFAFE",
            "--color-surface-selected": "#ECFEFF",
        },
    },
}

_active_theme: ThemeName = "dark"
_active_accent: AccentName = "blue"


def tokens_for(
    theme: ThemeName,
    accent: AccentName | str | None = None,
) -> dict[str, str]:
    base = dict(DARK_TOKENS if theme == "dark" else LIGHT_TOKENS)

    chosen = str(accent or _active_accent)

    if chosen not in ACCENT_OVERRIDES:
        chosen = "blue"

    base.update(ACCENT_OVERRIDES[chosen][theme])

    # Shared presentation roles: QSS and custom painters use the same palette.
    base.update({
        "--color-kpi": base["--color-primary"] if chosen == "neon" else base["--color-text"],
        "--color-hud-line": base["--color-primary"],
        "--color-hud-grid": base["--color-border"],
        "--color-panel-top": base["--color-surface-selected"] if chosen == "neon" else base["--color-surface"],
        "--kpi-font-size": "32pt" if chosen == "neon" else "20pt",
        "--panel-radius": "3px" if chosen == "neon" else "12px",
    })

    return base


def set_active_theme(theme: ThemeName) -> None:
    global _active_theme
    _active_theme = theme


def active_theme() -> ThemeName:
    return _active_theme


def set_active_accent(accent: AccentName | str) -> None:
    global _active_accent
    _active_accent = accent if accent in ACCENT_OVERRIDES else "blue"


def active_accent() -> AccentName:
    return _active_accent


def hud_enabled() -> bool:
    return _active_accent == "neon"


def glow_enabled() -> bool:
    return hud_enabled() and _active_theme == "dark"


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


def race_palette(theme: ThemeName, accent: AccentName | str) -> tuple[str, str, str]:
    tokens = tokens_for(theme, accent)
    # Keep all three series distinguishable when the accent matches another color.
    secondary = tokens_for(theme, 'purple')["--color-primary"] if accent == 'gold' else tokens["--color-warning"]
    tertiary = tokens_for(theme, 'emerald' if accent == 'magenta' else 'magenta')["--color-primary"]
    return tokens["--color-primary"], secondary, tertiary
