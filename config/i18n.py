from __future__ import annotations

import json
import re
from pathlib import Path

LANGUAGES = {'en': 'English', 'ko': '한국어', 'ja': '日本語'}
_language = 'en'
_phrases = {}
_pattern = None
_rows = json.loads((Path(__file__).parent / 'translations.json').read_text(encoding='utf-8'))
_exact = {text: row for row in _rows for text in row.values()}


def set_language(language: str) -> None:
    global _language, _phrases, _pattern
    _language = language if language in LANGUAGES else 'en'
    _phrases = {source: row[_language] for row in _rows for source in row.values()
                if (len(source) >= 5 or source != source.strip()) and source != row[_language] and (' ' in source or any(ord(c) > 127 for c in source))}
    pattern = '|'.join((r'(?<![A-Za-z])' if s[0].isascii() and s[0].isalpha() else '')
                       + re.escape(s) + (r'(?![A-Za-z])' if s[-1].isascii() and s[-1].isalpha() else '')
                       for s in sorted(_phrases, key=len, reverse=True))
    _pattern = re.compile(pattern)


def tr(text):
    """Translate presentation text only; source data and metric keys stay intact."""
    if not isinstance(text, str) or not text:
        return text
    inning = re.fullmatch(r'(\d+)회([초말])|(?:(Top|Bottom) (\d+))|(\d+)回([表裏])', text)
    if inning:
        number = inning[1] or inning[4] or inning[5]
        top = inning[2] == '초' or inning[3] == 'Top' or inning[6] == '表'
        return {'en': f"{'Top' if top else 'Bottom'} {number}",
                'ko': f"{number}회{'초' if top else '말'}",
                'ja': f"{number}回{'表' if top else '裏'}"}[_language]
    if text in _exact:
        return _exact[text][_language]
    # Rendered status sentences include names/numbers. Replace only catalog phrases,
    # using word boundaries for Latin phrases, never arbitrary metric substrings.
    return _pattern.sub(lambda m: _phrases[m.group()], text) if _pattern else text


set_language('en')


def tr_list(items):
    return [tr(item) for item in items]


def translate_widgets(root) -> None:
    """Retranslate existing controls when the language setting changes."""
    from PyQt6.QtCore import QSignalBlocker
    from PyQt6.QtWidgets import (QWidget, QLabel, QAbstractButton, QGroupBox, QLineEdit,
                               QComboBox, QTabWidget, QTableWidget, QListWidget)
    for widget in [root, *root.findChildren(QWidget)]:
        blocker = QSignalBlocker(widget)
        widget.setToolTip(tr(widget.toolTip()))
        widget.setAccessibleName(tr(widget.accessibleName()))
        widget.setAccessibleDescription(tr(widget.accessibleDescription()))
        if isinstance(widget, (QLabel, QAbstractButton)):
            widget.setText(tr(widget.text()))
        if isinstance(widget, QGroupBox):
            widget.setTitle(tr(widget.title()))
        if isinstance(widget, QLineEdit):
            widget.setPlaceholderText(tr(widget.placeholderText()))
        if isinstance(widget, QComboBox):
            for i in range(widget.count()):
                widget.setItemText(i, tr(widget.itemText(i)))
        if isinstance(widget, QTabWidget):
            for i in range(widget.count()):
                widget.setTabText(i, tr(widget.tabText(i)))
        if isinstance(widget, QListWidget):
            for i in range(widget.count()):
                item = widget.item(i)
                item.setText(tr(item.text()))
                item.setToolTip(tr(item.toolTip()))
        if isinstance(widget, QTableWidget):
            items = [widget.horizontalHeaderItem(i) for i in range(widget.columnCount())]
            items += [widget.item(r, c) for r in range(widget.rowCount()) for c in range(widget.columnCount())]
            for item in items:
                if item:
                    item.setText(tr(item.text()))
                    item.setToolTip(tr(item.toolTip()))
        del blocker
