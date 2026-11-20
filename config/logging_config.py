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
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    if not any(getattr(handler, "_dugout_role", None) == "console" for handler in root.handlers):
        console = logging.StreamHandler()
        console._dugout_role = "console"
        console.addFilter(PrivateDataFilter())
        console.setFormatter(formatter)
        root.addHandler(console)
    if any(getattr(handler, "_dugout_role", None) == "file" for handler in root.handlers):
        return
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            LOG_DIR / "dugout_atlas.log",
            maxBytes=2_000_000,
            backupCount=5,
            encoding="utf-8",
        )
    except OSError:
        root.error("Cannot open application file log; console logging remains available")
        return
    file_handler._dugout_role = "file"
    file_handler.addFilter(PrivateDataFilter())
    file_handler.setFormatter(formatter)

    root.addHandler(file_handler)
