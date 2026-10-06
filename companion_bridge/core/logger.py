"""
AirDeck Core Logging Subsystem
Provides structured console and rotating file logging to %APPDATA%/AirDeck/logs.
"""

import logging
from logging.handlers import RotatingFileHandler
import os
import sys
from pathlib import Path


def get_log_dir() -> Path:
    """Resolve the persistent log directory for AirDeck."""
    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA")
        if app_data:
            base_dir = Path(app_data) / "AirDeck" / "logs"
        else:
            base_dir = Path.home() / ".airdeck" / "logs"
    else:
        base_dir = Path.home() / ".airdeck" / "logs"

    try:
        base_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Fallback to local logs directory if system directory is inaccessible
        base_dir = Path(__file__).parent.parent / "logs"
        base_dir.mkdir(parents=True, exist_ok=True)

    return base_dir


def setup_logger(name: str = "AirDeck") -> logging.Logger:
    """Configure structured logger with console and rotating file handlers."""
    log = logging.getLogger(name)
    if log.handlers:
        return log

    log.setLevel(logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 1. Console Stream Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    log.addHandler(console_handler)

    # 2. Rotating File Handler (Max 5MB per file, 3 backups)
    try:
        log_dir = get_log_dir()
        log_file = log_dir / "airdeck.log"
        file_handler = RotatingFileHandler(
            str(log_file),
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        log.addHandler(file_handler)
    except Exception as e:
        print(f"[LOGGER WARNING] Could not initialize file handler: {e}")

    return log


# Global logger instance
logger = setup_logger("AirDeck")
