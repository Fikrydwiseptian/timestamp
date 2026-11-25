"""
Konfigurasi logging terpusat dengan rotasi file log.
"""

from __future__ import annotations
import logging
from logging.handlers import RotatingFileHandler
import sys
from app.utils.paths import get_logs_dir


_logger: logging.Logger | None = None


def get_logger(name: str = "GeoPhotoStamper") -> logging.Logger:
    """Mengembalikan instance logger aplikasi yang telah dikonfigurasi."""
    global _logger
    if _logger is not None:
        return logging.getLogger(f"GeoPhotoStamper.{name}") if name != "GeoPhotoStamper" else _logger

    logger = logging.getLogger("GeoPhotoStamper")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        # Formatter
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # File Handler (Maksimal 2 MB per file, simpan 3 file backup)
        log_file = get_logs_dir() / "app.log"
        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    _logger = logger
    return logging.getLogger(f"GeoPhotoStamper.{name}") if name != "GeoPhotoStamper" else _logger
