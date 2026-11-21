from __future__ import annotations
from config.theme_tokens import tokens_for

def test_gold_accent_preserves_semantic_colors() -> None:
    base=tokens_for("dark","blue")
    gold=tokens_for("dark","gold")
    assert gold["--color-primary"] == "#D6B36A"
    assert gold["--color-success"] == base["--color-success"]
    assert gold["--color-danger"] == base["--color-danger"]


def test_slate_dark_tokens_and_component_exports() -> None:
    from charts import ModernSplineChart
    from ui.components import BaseballDiamondWidget, StatCard

    tokens = tokens_for("dark", "blue")
    assert tokens["--color-bg"] == "#0B1120"
    assert tokens["--color-surface"] == "#162032"
    assert tokens["--color-border"] == "#1E293B"
    assert tokens["--color-text"] == "#F8FAFC"
    assert tokens["--color-primary"] == "#38BDF8"
    assert all((ModernSplineChart, BaseballDiamondWidget, StatCard))
