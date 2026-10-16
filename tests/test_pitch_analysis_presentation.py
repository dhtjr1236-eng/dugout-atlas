"""Presentation regressions: summaries never mutate the analysis payload."""
from __future__ import annotations

from copy import deepcopy
import pytest
from PyQt6.QtWidgets import QApplication
from config.i18n import set_language, tr, translate_widgets
from config.theme_tokens import set_active_theme, set_active_accent, chart_colors
from services.pitch_analysis import analyze_pitches
from tests.test_pitch_analysis import actual
from ui.pitch_analysis_view import PitchAnalysisView


@pytest.fixture
def view():
    app = QApplication.instance() or QApplication([])
    set_language('en')
    widget = PitchAnalysisView()
    yield widget
    widget.close()
    app.processEvents()
    set_language('en')
    set_active_theme('dark')
    set_active_accent('blue')


def test_profile_starts_with_graph_and_optional_details(view):
    payload = analyze_pitches(actual(), 669373, 2025)
    saved = deepcopy(payload)
    view.set_result(payload)
    assert view.details.isHidden()
    assert view.profile.rowCount() > 0
    assert view.canvas.minimumHeight() >= 300
    annotations = [text.get_text() for text in view.figure.axes[0].texts]
    assert all('Md ' in text and '50% [' in text and 'mph' in text for text in annotations)
    assert 'Central 50%' in view.profile_summary.text()
    assert 'Valid N' in view.profile_sample.text()
    view.details_toggle.setChecked(True)
    assert not view.details.isHidden()
    view.metric.setCurrentIndex(1)
    assert all('rpm' in text.get_text() for text in view.figure.axes[0].texts)
    assert payload == saved


@pytest.mark.parametrize('language, caution, help_word', [
    ('en', 'Interpret with caution', 'middle value'),
    ('ko', '해석 주의', '가운데 값'),
    ('ja', '解釈に注意', '中央の値'),
])
def test_live_translation_help_and_small_denominators(view, language, caution, help_word):
    view.set_result(analyze_pitches(actual().iloc[:4].copy(), 669373, 2025))
    set_language(language)
    translate_widgets(view)
    assert caution in view.profile_sample.text()
    assert caution in view.match_sample.text()
    assert help_word in view.profile.horizontalHeaderItem(4).toolTip()
    assert view.details_toggle.text() == tr('Show details')
    assert view.match_choice.count() > 0
    row = view.payload['matchup']['hand']['rows'][0]
    assert f"{row['whiffs']}/{row['swings']}" in view.match_summary.text()
    assert str(row['pitches']) in view.match_sample.text()
    assert view.matchup.item(0, 5).text().startswith(f"{row['whiffs']}/{row['swings']}")


def test_zero_swings_stays_uncalculated(view):
    frame = actual().iloc[:3].copy()
    frame['description'] = 'called_strike'
    payload = analyze_pitches(frame, 669373, 2025)
    saved = deepcopy(payload)
    view.set_result(payload)
    assert 'Not calculated' in view.match_summary.text()
    assert '0/0' in view.match_summary.text()
    assert all(row['whiff'] is None for row in payload['matchup']['hand']['rows'])
    assert payload == saved


@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_theme_and_narrow_layout_preserve_values(view, theme):
    payload = analyze_pitches(actual(), 669373, 2025)
    saved = deepcopy(payload)
    set_active_theme(theme)
    set_active_accent('gold')
    view.set_result(payload)
    view.resize(640, 800)
    assert view.profile_summary.wordWrap()
    assert view.match_summary.wordWrap()
    assert view.figure.axes[0].xaxis.label.get_color() == chart_colors()['text']
    assert payload == saved

# Dugout Atlas
# Copyright (c) 2026 dhtjr1236-eng
# Unauthorized redistribution or rebranding is prohibited.
