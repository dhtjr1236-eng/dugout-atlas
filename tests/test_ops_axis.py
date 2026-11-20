from __future__ import annotations

from dataclasses import replace
import math
import pytest
from PyQt6.QtCore import QDate

from services.race_presentation import period_extrema, validate_limits
from tests.test_ops_race_ui import view, result


def test_manual_checkbox_zoom_unzoom_and_clipped_marker(view):
    w, _ = view
    w._ops_loaded(result())
    automatic = w.figure.axes[0].get_ylim()
    assert not w.axis_min.isEnabled()
    w.manual_axis.setChecked(True)
    assert w.axis_min.isEnabled()
    assert w.figure.axes[0].get_ylim() == (.7, 1.2)
    assert any('Outside axis' in t.get_text() for t in w.figure.axes[0].texts)
    assert '1.350' in w.summary_cards[0].text()
    w.slider.setValue(0)
    assert w.figure.axes[0].get_ylim() == (.7, 1.2)
    w.manual_axis.setChecked(False)
    assert w.figure.axes[0].get_ylim() == automatic
    assert not w.axis_min.isEnabled()


def test_controls_never_allow_reversed_or_zero_range(view):
    w, _ = view
    w.manual_axis.setChecked(True)
    w.axis_min.setValue(2)
    assert w.axis_min.value() < w.axis_max.value()
    w.axis_max.setValue(0)
    assert w.axis_min.value() == 0 and w.axis_max.value() > 0
    w.axis_min.setValue(5)
    assert 0 <= w.axis_min.value() < w.axis_max.value() <= 5


def test_period_extrema_use_unsampled_daily_points_and_date_filter(view):
    w, _ = view
    data = result()
    series = [dict(p) for p in data.points]
    series[0]['2025-04-02'] = replace(series[0]['2025-04-02'], value=1.8)
    data = replace(data, points=tuple(series))
    w._ops_loaded(data)
    w.granularity.setCurrentIndex(0)  # Only month-end is plotted.
    assert len(w.points[0]) == 1
    assert w._period_peaks[0][0].day == '2025-04-02'
    assert '1.800 (2025-04-02)' in w.extrema_label.text()
    w.range_start.setDate(QDate(2025, 4, 3)); w.range_end.setDate(QDate(2025, 4, 3))
    w.range_enabled.setChecked(True)
    assert w._period_peaks[0][0].day == '2025-04-03'
    w.metric.setCurrentIndex(0)
    assert w.ops_axis_controls.isHidden() and w.extrema_label.isHidden()


def test_extrema_ties_empty_and_axis_validation():
    points = result().points[0]
    high, low = period_extrema(points.values(), '2025-04-01', '2025-04-03')
    assert high.day == low.day == '2025-04-01'
    assert period_extrema([], '2025-04-01', '2025-04-03') is None
    for pair in [(1,1),(2,1),(-1,1),(0,6),(math.nan,1),(0,math.inf)]:
        with pytest.raises(ValueError): validate_limits(*pair)
