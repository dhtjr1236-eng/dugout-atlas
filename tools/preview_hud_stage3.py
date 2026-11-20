"""Offline fictional race preview using real UI and production animation exporter."""
import argparse
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    with tempfile.TemporaryDirectory(prefix='dugout-stage3-') as temporary:
        os.environ['LOCALAPPDATA'] = temporary
        from PyQt6.QtCore import QSettings
        from PyQt6.QtGui import QFontDatabase
        from PyQt6.QtWidgets import QApplication
        from config import preferences
        preferences.store = lambda: QSettings(str(Path(temporary) / 'settings.ini'), QSettings.Format.IniFormat)
        preferences.save_preferences({'data_root':str(Path(temporary)/'runtime'),'language':'ko'})
        from config.i18n import set_language
        set_language('ko')
        app = QApplication([])
        for name in ('segoeui.ttf','segoeuib.ttf','malgun.ttf','malgunbd.ttf'):
            path = Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/name
            if path.is_file(): QFontDatabase.addApplicationFont(str(path))
        from config.settings import THEME_QSS_PATH
        from ui.theme_manager import ThemeManager
        from ui.season_race_view import SeasonRaceView
        from services.season_race import SeasonAxis, Point, RacePlayer
        from services.race_animation import export_animation, AnimationOptions
        manager = ThemeManager(app,THEME_QSS_PATH.read_text(encoding='utf-8'))
        manager.set_accent('neon')
        manager.apply('dark',animate=False)
        window = SeasonRaceView(SimpleNamespace(fangraphs=SimpleNamespace(db=SimpleNamespace())),demo_only=True)
        manager.add_listener(window._draw)
        dates = tuple(f'2025-{month:02d}-01' for month in range(4,10))
        window.axis = SeasonAxis(2025,dates[0],dates[-1],dates)
        window.players = [RacePlayer(1,'Demo A','bat'),RacePlayer(2,'Demo B','bat')]
        window.points = [{day:Point(day,value,'Example') for day,value in zip(dates,values) if value is not None}
                         for values in ((1.,2.,None,2.8,4.2,5.4),(.8,1.5,2.5,2.2,3.1,3.8))]
        window.slider.setRange(0,len(dates)-1)
        window.slider.setValue(len(dates)-1)
        window.resize(1440,1000)
        window.show()
        for theme in ('dark','light'):
            manager.apply(theme,animate=False)
            window._draw()
            for _ in range(6): app.processEvents()
            window.save_image(args.output/f'race-neon-{theme}.png')
        manager.apply('dark',animate=False)
        frozen = window.animation_snapshot()
        from dataclasses import replace
        frozen = replace(frozen,font=str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/'malgun.ttf'))
        export_animation(frozen,AnimationOptions(seconds=6,fps=5,width=960),args.output/'neon-demo.gif',threading.Event())
        from PIL import Image
        with Image.open(args.output/'neon-demo.gif') as animation:
            animation.seek(animation.n_frames - 1)
            animation.convert('RGB').save(args.output/'video-last-frame.png')
        window.close()


if __name__ == '__main__':
    from multiprocessing import freeze_support
    freeze_support()
    main()
