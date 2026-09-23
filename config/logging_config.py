from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler

from config.settings import LOG_DIR


class PrivateDataFilter(logging.Filter):
    """Remove common credential and home-directory patterns before output."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        message = re.sub(r"(https?://[^\s?]+)\?[^\s]+", r"\1?[redacted]", message)
        message = re.sub(r"(?i)(authorization|token|api[_-]?key|password)\s*[:=]\s*[^\s,;]+",
                         r"\1=[redacted]", message)
        message = re.sub(r"(?i)[a-z]:\\Users\\[^\\\s]+", r"[home]", message)
        message = re.sub(r"/(?:home|Users)/[^/\s]+", "[home]", message)
        record.msg = message
        record.args = ()
        return True


def configure_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    console = logging.StreamHandler()
    console.addFilter(PrivateDataFilter())
    console.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        LOG_DIR / "app.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.addFilter(PrivateDataFilter())
    file_handler.setFormatter(formatter)

    root.addHandler(console)
    root.addHandler(file_handler)
