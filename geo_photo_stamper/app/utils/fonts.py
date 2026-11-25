"""
Manajemen font untuk render teks overlay Geo Photo Stamper.
"""

from __future__ import annotations
import os
from pathlib import Path
from PIL import ImageFont
from app.utils.logger import get_logger

logger = get_logger("Fonts")

# Daftar font umum di Windows
SYSTEM_FONT_CANDIDATES = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/tahoma.ttf",
    "C:/Windows/Fonts/calibri.ttf",
    "C:/Windows/Fonts/consola.ttf",
]


def get_available_system_fonts() -> list[str]:
    """Mengembalikan daftar nama font yang tersedia di sistem."""
    found = []
    for p in SYSTEM_FONT_CANDIDATES:
        if os.path.exists(p):
            found.append(Path(p).stem.capitalize())
    if not found:
        found.append("Default")
    return found


def load_font(font_name_or_path: str | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Memuat font TrueType berdasarkan nama atau path file.
    Jika gagal, akan fallback ke font standar sistem atau ImageFont default.
    """
    size = max(8, int(size))
    
    # 1. Cek jika path langsung diberikan dan ada
    if font_name_or_path and os.path.exists(font_name_or_path):
        try:
            return ImageFont.truetype(font_name_or_path, size=size)
        except Exception as e:
            logger.warning(f"Gagal memuat font dari path '{font_name_or_path}': {e}")

    # 2. Cek nama font di folder Windows Fonts
    if font_name_or_path and font_name_or_path.lower() != "default":
        win_fonts = Path("C:/Windows/Fonts")
        candidate = win_fonts / f"{font_name_or_path.lower()}.ttf"
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size=size)
            except Exception as e:
                logger.warning(f"Gagal memuat font '{candidate}': {e}")

    # 3. Coba kandidat font Windows bawaan
    for p in SYSTEM_FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size=size)
            except Exception:
                continue

    # 4. Fallback absolut
    return ImageFont.load_default()
