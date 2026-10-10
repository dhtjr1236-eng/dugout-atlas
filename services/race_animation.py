"""Offline animation export, isolated from Qt and the live chart renderer."""
from __future__ import annotations

from dataclasses import dataclass
import multiprocessing as mp
import os
from pathlib import Path
import tempfile
import threading
from collections.abc import Callable

from PIL import Image, ImageDraw, ImageFont, features


@dataclass(frozen=True)
class AnimationOptions:
    format: str = 'GIF'
    seconds: int = 8
    fps: int = 10
    width: int = 960
    loop: bool = True

    def validate(self) -> None:
        if self.format not in ('GIF', 'WEBP') or not 6 <= self.seconds <= 12 or self.fps not in (5, 10) or self.width not in (640, 960):
            raise ValueError('Invalid animation options')
        if self.format == 'WEBP' and not features.check('webp'):
            raise ValueError('WebP is unavailable in this Pillow build')


@dataclass(frozen=True)
class RaceSnapshot:
    dates: tuple[str, ...]
    values: tuple[tuple[float | None, ...], ...]
    names: tuple[str, ...]
    metric: str
    season: int
    limits: tuple[float, float]
    dark: bool = False
    font: str = ''
    footer: str = ''
    extrema: tuple[str, ...] = ()


def render_frame(snapshot: RaceSnapshot, index: int, width: int) -> Image.Image:
    """Render only acquired samples; gaps are not filled with invented values."""
    height = width * 9 // 16
    scale = width / 960
    bg, fg, grid = ('#0B1220', '#E5E7EB', '#334155') if snapshot.dark else ('#F5F7FB', '#172033', '#D9E1EC')
    im = Image.new('RGB', (width, height), bg)
    draw = ImageDraw.Draw(im)
    def font(size):
        try:
            return ImageFont.truetype(snapshot.font, max(10, int(size * scale)))
        except OSError:
            return ImageFont.load_default(size=max(10, int(size * scale)))
    def text(x, y, value, size=18, color=fg):
        value = str(value)
        face = font(size)
        while draw.textlength(value, font=face) > width - x * scale - 16 and len(value) > 2:
            value = value[:-2] + '…'
        draw.text((int(x * scale), int(y * scale)), value, font=face, fill=color)
    text(24, 12, f'Dugout Atlas  ·  {snapshot.season}  ·  {snapshot.metric}', 24)
    text(24, 47, snapshot.dates[index], 20)
    colors = ('#3B82F6', '#E87935')
    for i, (name, values) in enumerate(zip(snapshot.names, snapshot.values)):
        value = values[index]
        label = '—' if value is None else f'{value:.3f}'
        text(24 + i * 455, 80, f'{name[:24]}   {label}', 22, colors[i])
        if i < len(snapshot.extrema):
            text(24 + i * 455, 112, snapshot.extrema[i], 14, colors[i])
    left, top, right, bottom = (int(v * scale) for v in (76, 156, 922, 439))
    low, high = snapshot.limits
    def xy(j, value):
        return left + (right-left)*j/max(1,len(snapshot.dates)-1), bottom-(bottom-top)*(value-low)/(high-low)
    for k in range(5):
        value = low + (high-low)*k/4
        y = xy(0, value)[1]
        draw.line((left,y,right,y), fill=grid)
        text(9, y/scale-9, f'{value:.3f}', 14)
    # Separate plot layer provides true clipping when a manual axis excludes values.
    layer = Image.new('RGB', (right-left+1, bottom-top+1), bg)
    painter = ImageDraw.Draw(layer)
    for k in range(5):
        y = (bottom-top)*k/4
        painter.line((0,y,right-left,y), fill=grid)
    for i, values in enumerate(snapshot.values):
        previous = None
        for j, value in enumerate(values[:index+1]):
            if value is None:
                previous = None
                continue
            x,y = xy(j,value); point=(x-left,y-top)
            if previous is not None:
                painter.line((*previous,*point), fill=colors[i], width=max(2,int(3*scale)))
            previous=point
        value=values[index]
        if value is not None:
            x,y=xy(index,value); x-=left; y-=top
            if low <= value <= high:
                r=6*scale
                painter.ellipse((x-r,y-r,x+r,y+r),fill=colors[i])
            else:
                y=0 if value>high else bottom-top
                direction=1 if value>high else -1
                painter.polygon([(x,y),(x-7,y+direction*12),(x+7,y+direction*12)],fill=colors[i])
    im.paste(layer,(left,top))
    text(76,448,snapshot.dates[0],14)
    text(810,448,snapshot.dates[-1],14)
    text(24,480,snapshot.footer,15)
    text(24,506,'OPS = OBP + SLG' if snapshot.metric=='OPS' else 'FanGraphs range samples',14)
    return im


def _encode(snapshot: RaceSnapshot, options: AnimationOptions, path: str, connection) -> None:
    """Child process: cancellation can terminate even a busy image encoder."""
    try:
        frames=[]
        total=options.seconds*options.fps
        for frame in range(total):
            index=round(frame*(len(snapshot.dates)-1)/(total-1))
            frames.append(render_frame(snapshot,index,options.width))
            connection.send(('render',frame+1,total))
        connection.send(('encode',total,total))
        kwargs={'save_all':True,'append_images':frames[1:],'duration':1000//options.fps}
        if options.loop or options.format=='WEBP':
            kwargs['loop']=0 if options.loop else 1
        if options.format=='WEBP':
            kwargs.update(lossless=True,method=3)
        frames[0].save(path,format=options.format,**kwargs)
        connection.send(('done',total,total))
    except Exception as exc:
        connection.send(('error',type(exc).__name__,0))
    finally:
        connection.close()


def export_animation(snapshot: RaceSnapshot, options: AnimationOptions, destination: Path,
                     cancel: threading.Event, progress: Callable = lambda value: None) -> bool:
    """Publish atomically on success; preserve existing files on cancel/failure."""
    options.validate()
    if not snapshot.dates or len(snapshot.names)!=2 or len(snapshot.values)!=2:
        raise ValueError('Two loaded players and dates are required')
    if any(len(values)!=len(snapshot.dates) for values in snapshot.values) or not snapshot.limits[0]<snapshot.limits[1]:
        raise ValueError('Invalid race snapshot')
    if cancel.is_set():
        return False
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    handle, temporary=tempfile.mkstemp(prefix='.race-',suffix='.tmp',dir=destination.parent)
    os.close(handle)
    context=mp.get_context('spawn')
    receiver,sender=context.Pipe(duplex=False)
    process=context.Process(target=_encode,args=(snapshot,options,temporary,sender),daemon=True)
    started=False
    success=False
    try:
        process.start(); started=True; sender.close()
        while True:
            if cancel.is_set():
                return False
            if receiver.poll(.05):
                try:
                    message=receiver.recv()
                except EOFError:
                    break
                if message[0]=='error':
                    raise RuntimeError('Animation encoding failed: '+message[1])
                if message[0]=='done':
                    success=True
                    break
                progress(message)
            elif not process.is_alive():
                break
        if not success:
            raise RuntimeError('Animation encoder stopped unexpectedly')
        if cancel.is_set():
            return False
        os.replace(temporary,destination)
        return True
    finally:
        if started:
            if process.is_alive():
                process.terminate()
            process.join()
        receiver.close(); sender.close()
        Path(temporary).unlink(missing_ok=True)
