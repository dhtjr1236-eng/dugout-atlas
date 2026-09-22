from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.figure import Figure

from config.theme_tokens import chart_colors


def _figure(title: str) -> tuple[Figure, Any]:
    colors = chart_colors()
    fig, ax = plt.subplots(figsize=(6.6, 3.6))
    fig.patch.set_facecolor(colors["figure"])
    ax.set_facecolor(colors["axes"])
    ax.tick_params(colors=colors["muted"])
    for spine in ax.spines.values():
        spine.set_color(colors["border"])
    ax.title.set_color(colors["text"])
    ax.xaxis.label.set_color(colors["muted"])
    ax.yaxis.label.set_color(colors["muted"])
    ax.set_title(title)
    fig.subplots_adjust(left=0.12, right=0.97, bottom=0.24, top=0.84)
    return fig, ax


def exit_velocity_distribution(statcast: dict[str, Any]) -> Figure:
    fig, ax = _figure("Exit Velocity Distribution")
    values = statcast.get("Exit Velocities") or []
    if values:
        sns.histplot(values, bins=18, kde=True, ax=ax)
        ax.set_xlabel("Exit velocity (mph)")
        ax.set_ylabel("Batted balls")
    else:
        ax.text(
            0.5,
            0.5,
            "No Statcast batted-ball data",
            ha="center",
            va="center",
            transform=ax.transAxes,
            color=chart_colors()["text"],
        )
    return fig


def quality_contact(statcast: dict[str, Any]) -> Figure:
    fig, ax = _figure("Barrel % / Hard Hit % / Sweet Spot %")
    labels = ["Barrel %", "Hard Hit %", "Sweet Spot %"]
    values = [float(statcast.get(label) or 0) for label in labels]
    ax.bar(labels, values)
    ax.set_ylabel("Percent")
    for idx, value in enumerate(values):
        ax.text(idx, value, f"{value:.1f}%", ha="center", va="bottom", color=chart_colors()["text"])
    return fig


def barrel_percentage(statcast: dict[str, Any]) -> Figure:
    fig, ax = _figure("Barrel %")
    value = statcast.get("Barrel %")
    if value is None:
        ax.text(0.5, 0.5, "No Barrel% data", ha="center", va="center", transform=ax.transAxes, color=chart_colors()["text"])
    else:
        number = float(value)
        ax.bar(["Barrel %"], [number])
        ax.set_ylim(0, max(20.0, number * 1.25))
        ax.set_ylabel("Percent")
        ax.text(0, number, f"{number:.1f}%", ha="center", va="bottom", color=chart_colors()["text"])
    return fig


def hard_hit_percentage(statcast: dict[str, Any]) -> Figure:
    fig, ax = _figure("Hard Hit %")
    value = statcast.get("Hard Hit %")
    if value is None:
        ax.text(0.5, 0.5, "No Hard-Hit% data", ha="center", va="center", transform=ax.transAxes, color=chart_colors()["text"])
    else:
        number = float(value)
        ax.bar(["Hard Hit %"], [number])
        ax.set_ylim(0, max(60.0, number * 1.2))
        ax.set_ylabel("Percent")
        ax.text(0, number, f"{number:.1f}%", ha="center", va="bottom", color=chart_colors()["text"])
    return fig


def _trend_rows(history: list[dict[str, Any]], metric: str) -> list[tuple[str, float]]:
    rows: list[tuple[str, float]] = []
    for row in history:
        period = row.get("Period", row.get("Season"))
        value = row.get(metric)
        if period is None or value is None:
            continue
        try:
            rows.append((str(period), float(value)))
        except (TypeError, ValueError):
            continue
    return rows


def _plot_trend(
    history: list[dict[str, Any]], metric: str, title: str, period_label: str
) -> Figure:
    fig, ax = _figure(f"{title} · {period_label}")
    rows = _trend_rows(history, metric)
    if not rows:
        ax.text(
            0.5,
            0.5,
            f"No {metric} trend data",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        return fig

    labels = [label for label, _value in rows]
    values = [value for _label, value in rows]
    x = list(range(len(labels)))
    ax.plot(x, values, marker="o")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45 if len(labels) > 8 else 0, ha="right" if len(labels) > 8 else "center")
    ax.set_xlabel("Period")
    ax.set_ylabel(metric)
    if metric == "wRC+":
        ax.axhline(100, linestyle="--", linewidth=1)
    return fig


def war_history(history: list[dict[str, Any]], period_label: str = "Yearly") -> Figure:
    return _plot_trend(history, "WAR", "fWAR Trend", period_label)


def wrc_history(history: list[dict[str, Any]], period_label: str = "Yearly") -> Figure:
    return _plot_trend(history, "wRC+", "wRC+ Trend", period_label)
