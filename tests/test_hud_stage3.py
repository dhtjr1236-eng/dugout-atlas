from dataclasses import replace
import math
from PIL import ImageColor

from config.theme_tokens import set_active_accent, set_active_theme, tokens_for, race_palette
from services.race_animation import RaceSnapshot, render_frame
from tests.test_ops_race_ui import view, result


def test_export_uses_captured_accent_and_leaves_gaps():
    snapshot = RaceSnapshot(('2025-04-01','2025-04-02','2025-04-03'),
                            ((.8,None,.8),(.5,None,.5)),('A','B'),'OPS',2025,(0.,1.),
                            dark=True, accent='neon')
    set_active_accent('gold')
    try:
        image = render_frame(snapshot, 2, 960)
        assert image.getpixel((0,0)) == ImageColor.getrgb(tokens_for('dark','neon')['--color-surface'])
        assert image.getpixel((8,8)) == ImageColor.getrgb(race_palette('dark','neon')[0])
        # The midpoint must not bridge two valid samples across a missing day.
        assert image.getpixel((499,213)) != ImageColor.getrgb('#00E5FF')
        light = render_frame(replace(snapshot, dark=False), 2, 960)
        assert light.getpixel((8,8)) == ImageColor.getrgb(race_palette('light','neon')[0])
    finally:
        set_active_accent('blue')


def test_live_lines_and_snapshot_share_palette_and_gaps(view):
    window, app = view
    set_active_theme('dark')
    set_active_accent('neon')
    try:
        window.granularity.setCurrentIndex(3)
        window._ops_loaded(result())
        dates = window.axis.dates
        window.points[0][dates[-1]] = replace(window.points[0][dates[0]], day=dates[-1])
        del window.points[0][dates[1]]
        window.slider.setValue(len(dates)-1)
        window._draw()
        frozen = window.animation_snapshot()
        assert frozen.accent == 'neon'
        assert frozen.values[0][1] is None
        line = next(line for line in window.figure.axes[0].lines if line.get_label() == 'Player A')
        assert math.isnan(line.get_ydata()[1])
        assert line.get_color() == race_palette('dark','neon')[0]
        assert any(line.get_label() == '_race_glow' for line in window.figure.axes[0].lines)
    finally:
        set_active_accent('blue')


def test_neon_animation_decodes_with_expected_palette(tmp_path):
    import threading
    from PIL import Image
    from services.race_animation import AnimationOptions, export_animation
    snapshot = RaceSnapshot(('2025-04-01','2025-04-02','2025-04-03'),
                            ((.8,None,.9),(.5,.6,.7)),('A','B'),'OPS',2025,(0.,1.), dark=True,accent='neon')
    path = tmp_path / 'neon.gif'
    assert export_animation(snapshot, AnimationOptions(seconds=6,fps=5,width=640), path, threading.Event())
    with Image.open(path) as animation:
        assert animation.n_frames >= 3
        assert animation.convert('RGB').getpixel((5,5)) == ImageColor.getrgb('#00E5FF')
