"""
Modul penggambaran kompas vektor dengan Pillow.
Menghasilkan gambar kompas berputar sesuai heading foto dengan background semi-transparan,
lingkaran skala, huruf arah mata angin (N, E, S, W), dan jarum kompas dwi-warna (merah-putih).
"""

from __future__ import annotations
import math
from PIL import Image, ImageDraw
from app.utils.fonts import load_font


def render_compass(heading: float | None, size: int = 200) -> Image.Image:
    """
    Menggambar kompas vektor berukuran size x size dengan sudut putar jarum sesuai heading.
    Jika heading None, kompas tetap digambar menunjuk ke Utara (heading=0) atau default.
    Menggunakan supersampling (2x) untuk hasil anti-aliasing yang tajam.
    """
    if size < 32:
        size = 32

    # Render pada resolusi 2x untuk anti-aliasing
    scale = 2
    canvas_size = size * scale
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    center = canvas_size / 2.0
    radius = (canvas_size / 2.0) - (8 * scale)

    # 1. Background Lingkaran Semi-transparan Gelap
    draw.ellipse(
        [center - radius, center - radius, center + radius, center + radius],
        fill=(15, 23, 42, 175),  # Slate dark semi-transparan
        outline=(255, 255, 255, 210),
        width=int(2.5 * scale)
    )

    # 2. Lingkaran cincin dalam tipis
    inner_radius = radius - (12 * scale)
    draw.ellipse(
        [center - inner_radius, center - inner_radius, center + inner_radius, center + inner_radius],
        outline=(255, 255, 255, 90),
        width=int(1.2 * scale)
    )

    # 3. Tanda Derajat / Ticks
    for deg in range(0, 360, 30):
        rad = math.radians(deg)
        tick_len = (8 * scale) if deg % 90 == 0 else (4 * scale)
        r_start = radius - (4 * scale)
        r_end = r_start - tick_len
        x1 = center + r_start * math.sin(rad)
        y1 = center - r_start * math.cos(rad)
        x2 = center + r_end * math.sin(rad)
        y2 = center - r_end * math.cos(rad)
        draw.line([(x1, y1), (x2, y2)], fill=(255, 255, 255, 180), width=int(1.5 * scale))

    # 4. Huruf Arah Mata Angin (N, E, S, W)
    font_size = int(14 * scale)
    font = load_font("Arial", font_size)
    cardinals = [("N", 0, (239, 68, 68, 255)),   # Merah untuk North
                 ("E", 90, (255, 255, 255, 230)),
                 ("S", 180, (255, 255, 255, 230)),
                 ("W", 270, (255, 255, 255, 230))]

    text_r = inner_radius - (10 * scale)
    for label, deg, col in cardinals:
        rad = math.radians(deg)
        tx = center + text_r * math.sin(rad)
        ty = center - text_r * math.cos(rad)
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((tx - tw / 2, ty - th / 2), label, fill=col, font=font)

    # 5. Jarum Kompas (Needle) Berputar Sesuai Heading
    angle_deg = float(heading) if heading is not None else 0.0
    needle_rad = math.radians(angle_deg)
    needle_len = inner_radius - (16 * scale)
    needle_width = 8 * scale

    # Titik ujung Utara (Needle Tip North)
    tip_n_x = center + needle_len * math.sin(needle_rad)
    tip_n_y = center - needle_len * math.cos(needle_rad)

    # Titik ujung Selatan (Needle Tip South)
    tip_s_x = center - needle_len * math.sin(needle_rad)
    tip_s_y = center + needle_len * math.cos(needle_rad)

    # Titik Sayap Kiri dan Kanan (Tegak lurus arah jarum)
    side_rad = needle_rad + math.pi / 2
    wing_l_x = center + needle_width * math.sin(side_rad)
    wing_l_y = center - needle_width * math.cos(side_rad)
    wing_r_x = center - needle_width * math.sin(side_rad)
    wing_r_y = center + needle_width * math.cos(side_rad)

    # Segitiga Utara (Merah Menyala)
    draw.polygon(
        [(tip_n_x, tip_n_y), (wing_l_x, wing_l_y), (center, center)],
        fill=(220, 38, 38, 240)
    )
    draw.polygon(
        [(tip_n_x, tip_n_y), (wing_r_x, wing_r_y), (center, center)],
        fill=(239, 68, 68, 255)
    )

    # Segitiga Selatan (Putih / Abu Elegan)
    draw.polygon(
        [(tip_s_x, tip_s_y), (wing_l_x, wing_l_y), (center, center)],
        fill=(203, 213, 225, 230)
    )
    draw.polygon(
        [(tip_s_x, tip_s_y), (wing_r_x, wing_r_y), (center, center)],
        fill=(241, 245, 249, 255)
    )

    # Garis tepi jarum
    draw.line([(tip_n_x, tip_n_y), (wing_l_x, wing_l_y), (tip_s_x, tip_s_y), (wing_r_x, wing_r_y), (tip_n_x, tip_n_y)],
              fill=(15, 23, 42, 200), width=1)

    # Titik Poros Tengah (Pivot Pin)
    pivot_r = 4.5 * scale
    draw.ellipse(
        [center - pivot_r, center - pivot_r, center + pivot_r, center + pivot_r],
        fill=(255, 255, 255, 255),
        outline=(30, 41, 59, 255),
        width=int(1.5 * scale)
    )

    # Resample down ke ukuran asli untuk anti-aliasing sempurna
    return img.resize((size, size), Image.Resampling.LANCZOS)
