"""
Modul render peta mini menggunakan tile OpenStreetMap.
Mendukung perhitungan Slippy Map (lat/lon ke tile X/Y), caching tile lokal ke disk,
penggabungan tile (stitching & cropping), gambar pin lokasi merah, dan atribusi wajib OSM.
"""

from __future__ import annotations
import math
import io
from pathlib import Path
import requests
from PIL import Image, ImageDraw
from app.utils.paths import get_tile_cache_dir
from app.utils.logger import get_logger
from app.utils.fonts import load_font

logger = get_logger("MapRenderer")

OSM_TILE_SERVER = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
USER_AGENT = "GeoPhotoStamper/1.0 (Sucofindo Desktop Tool; Windows)"


def _deg2num(lat_deg: float, lon_deg: float, zoom: int) -> tuple[float, float]:
    """Mengonversi derajat lat/lon ke koordinat floating tile x dan y."""
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = ((lon_deg + 180.0) / 360.0) * n
    # Batasi lat agar tidak melebihi batas proyeksi Web Mercator (-85.0511 ke 85.0511)
    lat_deg_clamped = max(-85.0511, min(85.0511, lat_deg))
    lat_rad = math.radians(lat_deg_clamped)
    ytile = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return (xtile, ytile)


def fetch_tile(z: int, x: int, y: int) -> Image.Image | None:
    """Mengambil satu tile peta OSM dari disk cache atau server online."""
    cache_dir = get_tile_cache_dir() / str(z) / str(x)
    cache_file = cache_dir / f"{y}.png"

    # 1. Cek disk cache
    if cache_file.exists():
        try:
            return Image.open(cache_file).convert("RGBA")
        except Exception as e:
            logger.debug(f"Gagal membaca tile cache {cache_file}: {e}")

    # 2. Unduh dari OSM
    url = OSM_TILE_SERVER.format(z=z, x=x, y=y)
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, timeout=4)
        if resp.status_code == 200:
            tile_img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
            cache_dir.mkdir(parents=True, exist_ok=True)
            tile_img.save(cache_file, format="PNG")
            return tile_img
    except Exception as e:
        logger.debug(f"Gagal mengunduh tile ({z}/{x}/{y}): {e}")

    return None


def _render_fallback_map(width: int, height: int) -> Image.Image:
    """Membuat peta pengganti berwarna abu-abu jika tile tidak tersedia secara offline."""
    img = Image.new("RGBA", (width, height), (226, 232, 240, 255))
    draw = ImageDraw.Draw(img)
    # Garis grid halus
    for x in range(0, width, 30):
        draw.line([(x, 0), (x, height)], fill=(203, 213, 225, 255), width=1)
    for y in range(0, height, 30):
        draw.line([(0, y), (width, y)], fill=(203, 213, 225, 255), width=1)
    return img


def draw_pin(draw: ImageDraw.ImageDraw, x: float, y: float, size: int = 24) -> None:
    """Menggambar pin lokasi merah presisi di titik (x, y)."""
    # Bayangan pin
    shadow_w = size * 0.7
    shadow_h = size * 0.3
    draw.ellipse(
        [x - shadow_w / 2, y - shadow_h / 2 + 2, x + shadow_w / 2, y + shadow_h / 2 + 2],
        fill=(0, 0, 0, 70)
    )

    # Badan Pin (Bentuk Pin Tetes Air / Lingkaran + Segitiga)
    pin_r = size * 0.45
    circle_center_y = y - size * 0.65

    # Segitiga bawah menunjuk titik (x, y)
    triangle = [
        (x - pin_r * 0.8, circle_center_y + pin_r * 0.3),
        (x + pin_r * 0.8, circle_center_y + pin_r * 0.3),
        (x, y)
    ]
    draw.polygon(triangle, fill=(220, 38, 38, 255))

    # Lingkaran atas
    draw.ellipse(
        [x - pin_r, circle_center_y - pin_r, x + pin_r, circle_center_y + pin_r],
        fill=(239, 68, 68, 255),
        outline=(185, 28, 28, 255),
        width=1
    )

    # Titik tengah putih pin
    inner_r = pin_r * 0.4
    draw.ellipse(
        [x - inner_r, circle_center_y - inner_r, x + inner_r, circle_center_y + inner_r],
        fill=(255, 255, 255, 255)
    )


def render_map(
    lat: float | None,
    lon: float | None,
    width: int = 260,
    height: int = 180,
    zoom: int = 15,
    border_radius: int = 10
) -> Image.Image:
    """
    Menghasilkan gambar peta mini yang berpusat pada (lat, lon) dengan pin merah dan atribusi OSM.
    Jika lat/lon None, mengembalikan peta fallback abu-abu dengan pin di tengah.
    """
    width = max(64, int(width))
    height = max(64, int(height))
    zoom = max(5, min(18, int(zoom)))

    if lat is None or lon is None:
        canvas = _render_fallback_map(width, height)
        draw = ImageDraw.Draw(canvas)
        draw_pin(draw, width / 2.0, height / 2.0, size=max(16, int(height * 0.18)))
        return canvas

    # Hitung posisi tile pusat
    center_xtile, center_ytile = _deg2num(lat, lon, zoom)
    center_tile_x_int = int(center_xtile)
    center_tile_y_int = int(center_ytile)

    # Jarak pixel pusat relatif terhadap tile pusat
    pixel_offset_x = (center_xtile - center_tile_x_int) * 256.0
    pixel_offset_y = (center_ytile - center_tile_y_int) * 256.0

    # Rentang tile yang perlu dimuat di sekitar tile pusat
    tile_span_x = int(math.ceil(width / 256.0)) + 1
    tile_span_y = int(math.ceil(height / 256.0)) + 1

    min_tx = center_tile_x_int - tile_span_x // 2
    max_tx = center_tile_x_int + tile_span_x // 2
    min_ty = center_tile_y_int - tile_span_y // 2
    max_ty = center_tile_y_int + tile_span_y // 2

    # Canvas besar untuk menampung tile
    big_w = (max_tx - min_tx + 1) * 256
    big_h = (max_ty - min_ty + 1) * 256
    big_img = Image.new("RGBA", (big_w, big_h), (226, 232, 240, 255))

    n_max = 2 ** zoom
    any_tile_loaded = False

    for tx in range(min_tx, max_tx + 1):
        for ty in range(min_ty, max_ty + 1):
            clamped_tx = tx % n_max
            if 0 <= ty < n_max:
                tile = fetch_tile(zoom, clamped_tx, ty)
                if tile:
                    any_tile_loaded = True
                    px = (tx - min_tx) * 256
                    py = (ty - min_ty) * 256
                    big_img.paste(tile, (px, py))

    # Jika sama sekali tidak ada tile yang berhasil diunduh/cache
    if not any_tile_loaded:
        big_img = _render_fallback_map(big_w, big_h)

    # Hitung titik tengah pada canvas besar
    center_on_big_x = (center_tile_x_int - min_tx) * 256 + pixel_offset_x
    center_on_big_y = (center_tile_y_int - min_ty) * 256 + pixel_offset_y

    # Potong (crop) sebesar (width, height) tepat di tengah
    crop_x1 = int(center_on_big_x - width / 2.0)
    crop_y1 = int(center_on_big_y - height / 2.0)
    crop_x2 = crop_x1 + width
    crop_y2 = crop_y1 + height

    # Pastikan crop dalam batas
    cropped = big_img.crop((crop_x1, crop_y1, crop_x2, crop_y2))

    # Gambar Pin di tepat tengah peta
    draw = ImageDraw.Draw(cropped)
    pin_size = max(18, int(height * 0.18))
    draw_pin(draw, width / 2.0, height / 2.0, size=pin_size)

    # Atribusi OSM Wajib di kanan bawah peta mini
    attrib_text = "© OpenStreetMap"
    font_size = max(8, int(height * 0.055))
    font = load_font("Arial", font_size)
    bbox = draw.textbbox((0, 0), attrib_text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    pad = 3
    # Kotak latar belakang teks atribusi
    draw.rectangle(
        [width - tw - pad * 2 - 2, height - th - pad * 2 - 2, width - 2, height - 2],
        fill=(255, 255, 255, 190)
    )
    draw.text((width - tw - pad - 2, height - th - pad - 2), attrib_text, fill=(30, 41, 59, 255), font=font)

    # Garis tepi frame peta
    draw.rectangle([0, 0, width - 1, height - 1], outline=(255, 255, 255, 220), width=2)

    return cropped
