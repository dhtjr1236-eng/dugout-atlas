from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
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
    fig.subplots_adjust(left=0.12, right=0.97, bottom=0.20, top=0.84)
    return fig, ax


def pitch_usage(pitches: list[dict[str, Any]]) -> Figure:
    fig, ax = _figure("Pitch Usage")
    rows = [row for row in pitches if row.get("Usage %") is not None]
    if rows:
        labels = [str(row.get("pitch_type")) for row in rows]
        values = [float(row.get("Usage %") or 0) for row in rows]
        ax.pie(values, labels=labels, autopct="%1.1f%%", textprops={"color": chart_colors()["text"]})
    else:
        ax.text(0.5, 0.5, "No pitch data", ha="center", va="center", transform=ax.transAxes, color=chart_colors()["text"])
    return fig


def run_value(pitches: list[dict[str, Any]]) -> Figure:
    fig, ax = _figure("Run Value by Pitch")
    rows = [row for row in pitches if row.get("Run Value") is not None]
    if rows:
        labels = [str(row.get("pitch_type")) for row in rows]
        values = [float(row.get("Run Value") or 0) for row in rows]
        ax.bar(labels, values)
        ax.tick_params(axis="x", rotation=25)
        ax.set_ylabel("Runs prevented")
    else:
        ax.text(0.5, 0.5, "No run-value data", ha="center", va="center", transform=ax.transAxes, color=chart_colors()["text"])
    return fig


def velocity_history(history: list[dict[str, Any]]) -> Figure:
    """Plot Statcast primary-fastball velocity trend for the active period."""
    fig, ax = _figure("Average Fastball Velocity Trend")
    rows = [
        row for row in history
        if row.get("Period") is not None and row.get("Avg Velocity") is not None
    ]
    if rows:
        periods = [str(row["Period"]) for row in rows]
        values = [float(row.get("Avg Velocity") or 0) for row in rows]
        ax.plot(periods, values, marker="o")
        ax.tick_params(axis="x", rotation=30)
        ax.set_ylabel("mph")
        pitch = next((str(row.get("Pitch")) for row in rows if row.get("Pitch")), "Fastball")
        ax.set_xlabel(f"Period · {pitch}")
        if len(values) == 1:
            ax.scatter(periods, values)
    else:
        ax.text(
            0.5,
            0.5,
            "Statcast velocity history unavailable",
            ha="center",
            va="center",
            transform=ax.transAxes,
            color=chart_colors()["text"],
        )
    return fig


def whiff_by_pitch(pitches: list[dict[str, Any]]) -> Figure:
    fig, ax = _figure("Whiff % by Pitch")
    rows = [row for row in pitches if row.get("Whiff %") is not None]
    if rows:
        labels = [str(row.get("pitch_type")) for row in rows]
        values = [float(row.get("Whiff %") or 0) for row in rows]
        ax.bar(labels, values)
        ax.tick_params(axis="x", rotation=25)
        ax.set_ylabel("Whiff %")
    else:
        ax.text(0.5, 0.5, "No Whiff% data", ha="center", va="center", transform=ax.transAxes, color=chart_colors()["text"])
    return fig
