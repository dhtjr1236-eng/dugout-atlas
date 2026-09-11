from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.figure import Figure


def _figure(title: str) -> tuple[Figure, Any]:
    fig, ax = plt.subplots(figsize=(6.6, 3.6))
    fig.patch.set_facecolor("#0d1626")
    ax.set_facecolor("#0d1626")
    ax.tick_params(colors="#d1d5db")
    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.title.set_color("#f8fafc")
    ax.xaxis.label.set_color("#cbd5e1")
    ax.yaxis.label.set_color("#cbd5e1")
    ax.set_title(title)
    fig.subplots_adjust(left=0.12, right=0.97, bottom=0.20, top=0.84)
    return fig, ax


def exit_velocity_distribution(statcast: dict[str, Any]) -> Figure:
    fig, ax = _figure("Exit Velocity Distribution")
    values = statcast.get("Exit Velocities") or []
    if values:
        sns.histplot(values, bins=18, kde=True, ax=ax)
        ax.set_xlabel("Exit velocity (mph)")
        ax.set_ylabel("Batted balls")
    else:
        ax.text(0.5, 0.5, "No Statcast batted-ball data", ha="center", va="center", transform=ax.transAxes)
    return fig


def quality_contact(statcast: dict[str, Any]) -> Figure:
    fig, ax = _figure("Barrel % / Hard Hit % / Sweet Spot %")
    labels = ["Barrel %", "Hard Hit %", "Sweet Spot %"]
    values = [float(statcast.get(label) or 0) for label in labels]
    ax.bar(labels, values)
    ax.set_ylabel("Percent")
    for idx, value in enumerate(values):
        ax.text(idx, value, f"{value:.1f}%", ha="center", va="bottom", color="#e5e7eb")
    return fig


def barrel_percentage(statcast: dict[str, Any]) -> Figure:
    fig, ax = _figure("Barrel %")
    value = statcast.get("Barrel %")
    if value is None:
        ax.text(0.5, 0.5, "No Barrel% data", ha="center", va="center", transform=ax.transAxes)
    else:
        number = float(value)
        ax.bar(["Barrel %"], [number])
        ax.set_ylim(0, max(20.0, number * 1.25))
        ax.set_ylabel("Percent")
        ax.text(0, number, f"{number:.1f}%", ha="center", va="bottom", color="#e5e7eb")
    return fig


def hard_hit_percentage(statcast: dict[str, Any]) -> Figure:
    fig, ax = _figure("Hard Hit %")
    value = statcast.get("Hard Hit %")
    if value is None:
        ax.text(0.5, 0.5, "No Hard-Hit% data", ha="center", va="center", transform=ax.transAxes)
    else:
        number = float(value)
        ax.bar(["Hard Hit %"], [number])
        ax.set_ylim(0, max(60.0, number * 1.2))
        ax.set_ylabel("Percent")
        ax.text(0, number, f"{number:.1f}%", ha="center", va="bottom", color="#e5e7eb")
    return fig

def war_history(history: list[dict[str, Any]]) -> Figure:
    fig, ax = _figure("Year-by-Year fWAR")
    rows = [row for row in history if row.get("Season") is not None and row.get("WAR") is not None]
    if rows:
        years = [int(row["Season"]) for row in rows]
        values = [float(row["WAR"]) for row in rows]
        ax.plot(years, values, marker="o")
        ax.set_xlabel("Season")
        ax.set_ylabel("fWAR")
        ax.set_xticks(years)
    else:
        ax.text(0.5, 0.5, "No WAR history", ha="center", va="center", transform=ax.transAxes)
    return fig


def wrc_history(history: list[dict[str, Any]]) -> Figure:
    fig, ax = _figure("wRC+ Trend")
    rows = [row for row in history if row.get("Season") is not None and row.get("wRC+") is not None]
    if rows:
        years = [int(row["Season"]) for row in rows]
        values = [float(row["wRC+"]) for row in rows]
        ax.plot(years, values, marker="o")
        ax.axhline(100, linestyle="--", linewidth=1)
        ax.set_xlabel("Season")
        ax.set_ylabel("wRC+")
        ax.set_xticks(years)
    else:
        ax.text(0.5, 0.5, "No wRC+ history", ha="center", va="center", transform=ax.transAxes)
    return fig
