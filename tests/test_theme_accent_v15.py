from __future__ import annotations
from config.theme_tokens import tokens_for

def test_gold_accent_preserves_semantic_colors() -> None:
    base=tokens_for("dark","blue")
    gold=tokens_for("dark","gold")
    assert gold["--color-primary"] == "#D6B36A"
    assert gold["--color-success"] == base["--color-success"]
    assert gold["--color-danger"] == base["--color-danger"]
