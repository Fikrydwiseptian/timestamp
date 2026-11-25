"""
Pengelolaan preset gaya overlay Geo Photo Stamper.
Menyediakan konfigurasi default (gaya GPS Map Camera resmi),
serialisasi JSON, dan manajemen template tampilan.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, asdict, field
from typing import Any
from pathlib import Path


@dataclass
class OverlayStyle:
    """Konfigurasi gaya visual overlay pada foto."""
    # Posisi Elemen
    text_position: str = "bottom_right"      # "bottom_right", "bottom_left", "top_right", "top_left"
    map_position: str = "bottom_left"        # "bottom_left", "bottom_right", "top_left", "top_right", "hidden"
    compass_position: str = "top_left"       # "top_left", "top_right", "bottom_left", "bottom_right", "hidden"

    # Saklar Field Teks
    show_date_time: bool = True
    show_heading: bool = True
    show_street: bool = True
    show_district: bool = True
    show_regency_province: bool = True
    show_altitude: bool = True
    show_speed: bool = True
    show_index: bool = True
    show_coords: bool = True
    show_notes: bool = True

    # Peta dan Kompas
    show_map: bool = True
    map_width_pct: float = 0.24             # 24% dari lebar foto
    map_aspect_ratio: float = 0.72          # rasio tinggi terhadap lebar peta
    map_zoom: int = 15

    show_compass: bool = True
    compass_size_pct: float = 0.11          # 11% dari sisi terpendek foto

    # Gaya Tipografi & Latar
    font_name: str = "Arial"
    font_scale: float = 1.0                 # Skala pengali font
    text_color: str = "#FFFFFF"             # Putih bersih
    text_outline: bool = True
    outline_color: str = "#000000"
    show_bg_box: bool = True
    bg_box_color: str = "#000000"
    bg_box_opacity: int = 140               # 0 - 255 (semi transparan)

    # Format Tanggal
    date_format: str = "%d %b %Y %H.%M.%S"   # Contoh: 20 Mei 2022 14.09.07

    # Aturan Penomoran Indeks
    index_start: int = 1
    index_sort_by: str = "filename"         # "filename" atau "datetime"

    def to_dict(self) -> dict[str, Any]:
        """Konversi konfigurasi ke dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OverlayStyle:
        """Membuat instance OverlayStyle dari dictionary."""
        valid_fields = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    def to_json(self) -> str:
        """Serialisasi konfigurasi ke format JSON."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> OverlayStyle:
        """Deserialisasi konfigurasi dari format JSON."""
        return cls.from_dict(json.loads(json_str))


def get_default_style() -> OverlayStyle:
    """Mengembalikan konfigurasi gaya default (GPS Map Camera Style)."""
    return OverlayStyle()
