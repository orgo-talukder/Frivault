"""Privacy-preserving local logging setup."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from platformdirs import PlatformDirs

MAX_LOG_BYTES = 1_000_000
BACKUP_COUNT = 2


def configure_logging(log_directory: Path | None = None) -> logging.Logger:
    """Configure bounded local logs; callers must log codes, never user data."""

    logger = logging.getLogger("frivault")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if any(getattr(handler, "_frivault_handler", False) for handler in logger.handlers):
        return logger

    directory = log_directory or PlatformDirs("Frivault", appauthor=False).user_log_path
    try:
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            directory / "frivault.log",
            maxBytes=MAX_LOG_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        handler._frivault_handler = True  # type: ignore[attr-defined]
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    except OSError:
        logger.addHandler(logging.NullHandler())
    return logger
