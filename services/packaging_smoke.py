"""Opt-in, offline frozen-app check with isolated settings and user data."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import sys
import traceback


class PackagingSmoke:
    def __init__(self, argv):
        from PyQt6.QtCore import QSettings
        index = argv.index('--self-test')
        if index + 1 >= len(argv):
            raise ValueError('--self-test requires an absolute report.json path')
        self.report = Path(argv[index + 1])
        if not self.report.is_absolute():
            raise ValueError('Use an absolute report path')
        self.report.parent.mkdir(parents=True, exist_ok=True)
        self.runtime = self.report.parent / 'isolated-runtime'
        self.runtime.mkdir(exist_ok=True)
        os.environ['LOCALAPPDATA'] = str(self.runtime)
        os.environ['MPLCONFIGDIR'] = str(self.runtime / 'matplotlib')
        from config import preferences
        preferences.store = lambda: QSettings(str(self.runtime / 'preferences.ini'), QSettings.Format.IniFormat)
        settings = preferences.store()
        settings.setValue('preferences/data_root', str(self.runtime / 'Dugout Atlas'))
        settings.sync()

    def check(self, app, window, controller, db):
        result = {'ok': False, 'frozen': bool(getattr(sys, 'frozen', False)), 'checks': []}
        advanced = None
        try:
            from PyQt6.QtCore import Qt
            from config.paths import resource_path
            from config.settings import SETTINGS, DB_PATH
            from models.player import PlayerBundle, PlayerProfile
            from services.home_service import HomeSnapshot
            from services.season_race import SeasonAxis, Point
            from charts import ModernSplineChart
            from ui.components import StatCard, BaseballDiamondWidget
            result['version'] = SETTINGS.app_version
            for name in ('config/translations.json', 'config/theme.qss', 'config/brand_logo.png', 'database/schema.sql'):
                assert resource_path(name).is_file(), name
            assert DB_PATH.resolve().is_relative_to(self.runtime.resolve()), str(DB_PATH)
            with db.connection() as connection:
                assert connection.execute('SELECT 1').fetchone()[0] == 1
            result['checks'].append('resources and isolated SQLite')
            window.theme_manager.set_accent('neon')
            for theme in ('light', 'dark'):
                window.theme_manager.apply(theme, animate=False)
                app.processEvents()
            result['checks'].append('light/dark neon theme')
            chart = ModernSplineChart()
            chart.plot_trend([1, 2, 3, 4], [.7, .8, .75, .9], 'OPS')
            chart.fig.savefig(self.report.with_name('spline.png'))
            chart.close()
            result['checks'].append('NumPy SciPy Matplotlib spline')
            window._open_advanced_compare()
            advanced = window._advanced_compare_window
            advanced._add_slot()
            for i, slot in enumerate(advanced.slots):
                slot.player_id = i + 1
                slot.bundle = PlayerBundle(PlayerProfile(i + 1, f'Packaging Test {i + 1}'), basic={'ops': .7 + i / 10})
            advanced._sync_race(); advanced._render()
            race = advanced.race
            assert len(race.players) == 3
            race.axis = SeasonAxis(2026, '2026-04-01', '2026-04-02', ('2026-04-01', '2026-04-02'))
            race.points = [{day: Point(day, i + n / 10, 'SELF-TEST') for n, day in enumerate(race.axis.dates)} for i in range(3)]
            race.slider.setRange(0, 1); race.slider.setValue(1); race._draw()
            assert len(race.animation_snapshot().values) == 3
            advanced.slots[2].season.blockSignals(True)
            advanced.slots[2].season.setValue(advanced.slots[0].season.value() - 1)
            advanced.slots[2].season.blockSignals(False)
            advanced._sync_race()
            assert not advanced.tabs.isTabEnabled(1)
            result['checks'].append('three-player comparison and race rendering')

            csv_path = self.report.with_name('comparison.csv')
            assert advanced.csv_button.isEnabled()
            advanced._write_csv(csv_path, advanced._comparison_csv_contents())
            with csv_path.open(encoding='utf-8-sig', newline='') as stream:
                assert {row['mlbam_id'] for row in csv.DictReader(stream)} == {'1', '2', '3'}
            home = window.home_view
            favorites = (
                {'id': 1, 'name': 'Packaging Test 1', 'team': 'LAD'},
                {'id': 2, 'name': 'Packaging Test 2', 'team': 'NYY'},
            )
            home.set_snapshot(HomeSnapshot(home.season.value(), favorites, 0, 0, 0, ''))
            home.favorite_search.setText('nyy')
            assert home.favorites.count() == 1
            assert home.favorites.item(0).data(Qt.ItemDataRole.UserRole) == 2
            result['checks'].append('comparison CSV and favorite-player search')

            if not window.grab().save(str(self.report.with_name('app.png'))):
                raise RuntimeError('Could not capture main window')
            result['ok'] = True
        except Exception:
            result['error'] = traceback.format_exc()
        finally:
            if advanced is not None:
                advanced.close()
            self.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            window.close()
            app.exit(0 if result['ok'] else 1)
