from __future__ import annotations
import threading
from pathlib import Path
import time
import pytest
from PIL import Image, features
from services.race_animation import AnimationOptions, RaceSnapshot, export_animation
from tests.test_ops_race_ui import view, result


def snapshot():
    return RaceSnapshot(('2025-04-01','2025-04-02','2025-04-03'),
        ((.8,1.1,1.3),(None,.9,.95)),('Player A','Player B'),'OPS',2025,(.7,1.2))


@pytest.mark.parametrize('kind',['GIF','WEBP'])
def test_animation_decodes(tmp_path,kind):
    if kind=='WEBP' and not features.check('webp'):pytest.skip('WebP unavailable')
    output=tmp_path/f'race.{kind.lower()}'
    events=[]
    assert export_animation(snapshot(),AnimationOptions(kind,6,5,640),output,threading.Event(),events.append)
    with Image.open(output) as image:
        assert image.size==(640,360)
        assert image.n_frames>=3
        image.seek(0); first=image.convert('RGB').tobytes()
        image.seek(image.n_frames-1)
        assert image.convert('RGB').tobytes()!=first
    assert events[-1][0]=='encode'
    assert not list(tmp_path.glob('.race-*'))


@pytest.mark.parametrize('phase',['render','encode'])
def test_cancel_preserves_previous_file(tmp_path,phase):
    output=tmp_path/'race.gif'; output.write_bytes(b'original')
    event=threading.Event()
    def progress(message):
        if message[0]==phase:event.set()
    assert not export_animation(snapshot(),AnimationOptions(seconds=6,fps=5,width=640),output,event,progress)
    assert output.read_bytes()==b'original'
    assert not list(tmp_path.glob('.race-*'))


def test_failed_export_preserves_file(tmp_path):
    from dataclasses import replace
    output=tmp_path/'race.gif'; output.write_bytes(b'original')
    bad=replace(snapshot(),limits=(float('nan'),1))
    with pytest.raises(ValueError):export_animation(bad,AnimationOptions(),output,threading.Event())
    assert output.read_bytes()==b'original'


def test_ui_worker_keeps_events_responsive(view,tmp_path):
    from PyQt6.QtCore import QTimer
    w,app=view; w._ops_loaded(result()); w.manual_axis.setChecked(True)
    frozen=w.animation_snapshot()
    assert frozen.limits==pytest.approx((.7,1.2))
    output=tmp_path/'ui.gif'
    ticks=[]; timer=QTimer(); timer.timeout.connect(lambda:ticks.append(1)); timer.start(10)
    assert w.start_animation_export(output,AnimationOptions(seconds=6,fps=5,width=640))
    deadline=time.monotonic()+30
    while w._workers and time.monotonic()<deadline:
        app.processEvents(); time.sleep(.01)
    timer.stop()
    if w._workers:
        w.cancel()
        for thread in list(w._workers):thread.wait(10000)
        app.processEvents()
    assert output.exists()
    assert len(ticks)>3
    assert not w._workers
