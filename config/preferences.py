from __future__ import annotations

from PyQt6.QtCore import QSettings


def store() -> QSettings:
    return QSettings('Dugout Atlas', 'Dugout Atlas')


def read_preferences() -> dict:
    settings = store()
    def number(key, default, low, high):
        try:
            return max(low, min(high, int(settings.value('preferences/' + key, default))))
        except (TypeError, ValueError):
            return default
    language = str(settings.value('preferences/language', 'ko'))
    return {
        'refresh_seconds': number('refresh_seconds', 30, 15, 3600),
        'player_refresh_seconds': number('player_refresh_seconds', 300, 60, 3600),
        'font_scale': number('font_scale', 100, 80, 160),
        'notifications': str(settings.value('preferences/notifications', True)).lower() in {'true', '1'},
        'language': language if language in {'en', 'ko', 'ja'} else 'ko',
        'data_root': str(settings.value('preferences/data_root', '') or ''),
    }


def save_preferences(values: dict) -> None:
    settings = store()
    for key, value in values.items():
        settings.setValue('preferences/' + key, value)
    settings.sync()
    if settings.status() != QSettings.Status.NoError:
        raise OSError('Could not save settings')
