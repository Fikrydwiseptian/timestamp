"""
Manajemen path dan direktori aplikasi Geo Photo Stamper.
Mendukung direktori data pengguna di %APPDATA%/GeoPhotoStamper serta mode PyInstaller.
"""

from __future__ import annotations
import os
import sys
from pathlib import Path


def get_app_data_dir() -> Path:
    """Mengembalikan path direktori data aplikasi (%APPDATA%/GeoPhotoStamper)."""
    appdata = os.getenv("APPDATA")
    if appdata:
        base_dir = Path(appdata) / "GeoPhotoStamper"
    else:
        base_dir = Path.home() / ".geophotostamper"
    
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def get_db_path() -> Path:
    """Mengembalikan path file SQLite database."""
    return get_app_data_dir() / "geophotostamper.db"


def get_logs_dir() -> Path:
    """Mengembalikan direktori penyimpanan file log."""
    logs_dir = get_app_data_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def get_tile_cache_dir() -> Path:
    """Mengembalikan direktori cache tile OpenStreetMap."""
    cache_dir = get_app_data_dir() / "tile_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_presets_dir() -> Path:
    """Mengembalikan direktori penyimpanan preset JSON pengguna."""
    presets_dir = get_app_data_dir() / "presets"
    presets_dir.mkdir(parents=True, exist_ok=True)
    return presets_dir


def get_assets_dir() -> Path:
    """
    Mengembalikan path direktori assets.
    Mendukung lingkungan development dan bundle PyInstaller (sys._MEIPASS).
    """
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets"
    
    # Berada di geo_photo_stamper/app/utils/paths.py -> root adalah geo_photo_stamper/
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent
    assets_dir = project_root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    return assets_dir


def get_default_output_dir(input_dir: str | Path | None) -> Path:
    """
    Mengembalikan direktori output default (<input_dir>/stamped).
    Jika input_dir tidak valid, menggunakan Desktop/stamped.
    """
    if input_dir:
        p = Path(input_dir)
        if p.is_file():
            p = p.parent
        out = p / "stamped"
    else:
        out = Path.home() / "Desktop" / "stamped"
    
    out.mkdir(parents=True, exist_ok=True)
    return out
