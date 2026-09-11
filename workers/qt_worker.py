from __future__ import annotations

import asyncio
import inspect
import traceback
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal


class TaskThread(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, task: Callable[[], Any], parent: object | None = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self.task = task

    def run(self) -> None:
        try:
            result = self.task()
            if inspect.isawaitable(result):
                result = asyncio.run(result)
            self.succeeded.emit(result)
        except Exception:
            self.failed.emit(traceback.format_exc())
