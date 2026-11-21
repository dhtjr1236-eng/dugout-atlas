from __future__ import annotations

import asyncio
from io import BytesIO

from PIL import Image
from matplotlib.offsetbox import DrawingArea, OffsetImage
from cache.file_cache import HeadshotCache
from services import headshots
from ui.character_renderer import CharacterRenderer


def test_http_failure_vector_fallback(tmp_path, monkeypatch):
    async def fail(*args, **kwargs):
        raise OSError('HTTP 403')
    monkeypatch.setattr(headshots, 'async_get_bytes', fail)
    assert asyncio.run(headshots.load_headshot(123, HeadshotCache(tmp_path))) is None
    renderer = CharacterRenderer()
    marker = renderer.marker(123, 'Aaron', '#3366aa', 'headshot')
    assert isinstance(marker, DrawingArea)
    assert renderer.marker(123, 'Aaron', '#3366aa', 'headshot') is marker


def test_cached_circular_photo_no_second_download(tmp_path, monkeypatch):
    stream = BytesIO(); Image.new('RGBA',(60,60),'red').save(stream, format='PNG')
    calls=[]
    async def download(url, **kwargs):
        calls.append(url); return stream.getvalue()
    monkeypatch.setattr(headshots, 'async_get_bytes', download)
    cache=HeadshotCache(tmp_path)
    rgba=asyncio.run(headshots.load_headshot(123,cache))
    assert rgba.shape==(32,32,4) and rgba[0,0,3]==0 and rgba[16,16,3]==255
    assert cache.path_for(123)==tmp_path/'headshots'/'123.png'
    asyncio.run(headshots.load_headshot(123,cache))
    assert len(calls)==1 and '/people/123/headshot/' in calls[0]
    renderer=CharacterRenderer();renderer.set_headshot(123,rgba)
    marker=renderer.marker(123,'Aaron','#3366aa','headshot')
    assert isinstance(marker,OffsetImage)
    assert marker is renderer.marker(123,'Aaron','#3366aa','headshot')


def test_invalid_image_falls_back(tmp_path, monkeypatch):
    async def download(*args, **kwargs): return b'not an image'
    monkeypatch.setattr(headshots,'async_get_bytes',download)
    assert asyncio.run(headshots.load_headshot(123,HeadshotCache(tmp_path))) is None
    assert not HeadshotCache(tmp_path).path_for(123).exists()


def test_download_runs_off_gui_thread(monkeypatch):
    from types import SimpleNamespace
    from PyQt6.QtCore import QThread
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication
    from services.fangraphs_service import FanGraphsService
    from services.season_race import RacePlayer
    from tests.test_season_race import MemoryDB
    from ui import season_race_view
    app=QApplication.instance() or QApplication([])
    threads=[]
    async def download(pid):
        threads.append(QThread.currentThread() == app.thread())
        return None
    monkeypatch.setattr(season_race_view,'load_headshot',download)
    view=season_race_view.SeasonRaceView(SimpleNamespace(fangraphs=FanGraphsService(MemoryDB())))
    view.players=[RacePlayer(1,'A','bat')]
    view.marker_mode.setCurrentIndex(1)
    for _ in range(100):
        QTest.qWait(10)
        if not view._image_workers:
            break
    assert threads==[False] and not view._image_workers
    view.close()
