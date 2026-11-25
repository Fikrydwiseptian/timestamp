"""
Mesin utama penggambaran overlay stempel foto (Geo Photo Stamper).
Menggabungkan blok teks informasi lokasi/waktu, peta mini OSM dengan pin merah,
dan kompas vektor dengan penskalaan proporsional terhadap resolusi foto.
"""

from __future__ import annotations
import math
from datetime import datetime
from PIL import Image, ImageDraw, ImageColor
from app.core.exif_reader import PhotoMeta
from app.core.presets import OverlayStyle
from app.core.compass import render_compass
from app.core.map_renderer import render_map
from app.utils.fonts import load_font
from app.utils.logger import get_logger

logger = get_logger("OverlayEngine")

# Terjemahan nama bulan Indonesia untuk format tanggal cantik
INDONESIAN_MONTHS = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember"
}


def format_indonesian_date(dt_str: str) -> str:
    """Mengonversi string YYYY-MM-DD HH:MM:SS menjadi format '20 Mei 2022 14.09.07'."""
    if not dt_str:
        return ""
    try:
        # Coba parsing format umum
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                dt = datetime.strptime(dt_str.strip(), fmt)
                month_name = INDONESIAN_MONTHS.get(dt.month, str(dt.month))
                return f"{dt.day} {month_name} {dt.year} {dt.strftime('%H.%M.%S')}"
            except ValueError:
                continue
    except Exception:
        pass
    return dt_str


def heading_to_cardinal(heading: float | None) -> str:
    """Mengonversi derajat heading menjadi teks format '286° W'."""
    if heading is None:
        return ""
    deg = float(heading) % 360.0
    val = int((deg / 22.5) + 0.5) % 16
    directions = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"
    ]
    return f"{int(deg)}° {directions[val]}"


def _wrap_text_line(text: str, max_width: int, draw: ImageDraw.ImageDraw, font: Any) -> list[str]:
    """Membungkus teks otomatis jika melebihi max_width."""
    words = text.split()
    if not words:
        return []
    lines = []
    current_line = words[0]
    for w in words[1:]:
        test_line = f"{current_line} {w}"
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = w
    lines.append(current_line)
    return lines


def render_overlay(
    photo: Image.Image,
    meta: PhotoMeta,
    style: OverlayStyle
) -> Image.Image:
    """
    Menggambar overlay stempel lengkap pada foto:
    - Blok teks informasi di sudut (default: kanan bawah)
    - Peta mini OSM dengan pin merah di sudut (default: kiri bawah)
    - Kompas berputar di sudut (default: kiri atas)
    Mengembalikan salinan gambar baru dengan overlay.
    """
    # Buat salinan gambar dalam mode RGBA untuk compositing transparansi
    base_img = photo.copy().convert("RGBA")
    width, height = base_img.size
    min_dim = min(width, height)
    max_dim = max(width, height)

    # Lapisan overlay transparan
    overlay_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay_layer)

    # Margin dasar proporsional terhadap ukuran foto (~2% dari min_dim)
    margin = max(16, int(min_dim * 0.025))

    # =========================================================================
    # 1. PETA MINI
    # =========================================================================
    map_rendered_rect = None
    if style.show_map and style.map_position != "hidden":
        map_w = int(width * style.map_width_pct)
        map_w = max(140, min(int(width * 0.45), map_w))
        map_h = int(map_w * style.map_aspect_ratio)

        map_img = render_map(
            lat=meta.lat,
            lon=meta.lon,
            width=map_w,
            height=map_h,
            zoom=style.map_zoom
        )

        # Tentukan posisi peta
        if style.map_position == "bottom_left":
            map_x = margin
            map_y = height - margin - map_h
        elif style.map_position == "bottom_right":
            map_x = width - margin - map_w
            map_y = height - margin - map_h
        elif style.map_position == "top_left":
            map_x = margin
            map_y = margin
        elif style.map_position == "top_right":
            map_x = width - margin - map_w
            map_y = margin
        else:
            map_x = margin
            map_y = height - margin - map_h

        overlay_layer.paste(map_img, (map_x, map_y), map_img)
        map_rendered_rect = (map_x, map_y, map_w, map_h)

    # =========================================================================
    # 2. KOMPAS VEKTOR
    # =========================================================================
    if style.show_compass and style.compass_position != "hidden":
        compass_size = int(min_dim * style.compass_size_pct)
        compass_size = max(70, min(int(min_dim * 0.25), compass_size))

        compass_img = render_compass(meta.heading, size=compass_size)

        if style.compass_position == "top_left":
            comp_x = margin
            comp_y = margin
        elif style.compass_position == "top_right":
            comp_x = width - margin - compass_size
            comp_y = margin
        elif style.compass_position == "bottom_left":
            comp_x = margin
            comp_y = height - margin - compass_size
        elif style.compass_position == "bottom_right":
            comp_x = width - margin - compass_size
            comp_y = height - margin - compass_size
        else:
            comp_x = margin
            comp_y = margin

        overlay_layer.paste(compass_img, (comp_x, comp_y), compass_img)

    # =========================================================================
    # 3. BLOK TEKS INFORMASI
    # =========================================================================
    # Susun teks baris demi baris sesuai urutan spesifikasi PRD
    raw_lines: list[str] = []

    if style.show_date_time and meta.date_time:
        raw_lines.append(format_indonesian_date(meta.date_time))

    if style.show_heading and meta.heading is not None:
        raw_lines.append(heading_to_cardinal(meta.heading))

    if style.show_street and meta.street:
        raw_lines.append(meta.street)

    if style.show_district and meta.district and meta.district != "-":
        raw_lines.append(meta.district)

    if style.show_regency_province:
        loc_parts = []
        if meta.regency and meta.regency != "-":
            loc_parts.append(meta.regency)
        if meta.province and meta.province != "-":
            loc_parts.append(meta.province)
        if loc_parts:
            raw_lines.append(", ".join(loc_parts))

    if style.show_altitude and meta.altitude is not None:
        raw_lines.append(f"Ketinggian: {meta.altitude:.1f} m")

    if style.show_speed and meta.speed is not None:
        raw_lines.append(f"Kecepatan: {meta.speed:.1f} km/h")

    if style.show_coords and meta.lat is not None and meta.lon is not None:
        raw_lines.append(f"GPS: {meta.lat:.5f}, {meta.lon:.5f}")

    if style.show_index:
        raw_lines.append(f"No. {meta.index_no}")

    if style.show_notes and meta.notes:
        raw_lines.append(f"Catatan: {meta.notes}")

    if raw_lines:
        # Hitung ukuran font dasar proporsional terhadap min_dim (~2.1% dari min_dim)
        base_font_size = int(min_dim * 0.021 * style.font_scale)
        base_font_size = max(11, base_font_size)

        # Lebar maksimal blok teks (misal 50% lebar foto jika berdampingan dengan peta)
        max_text_block_width = int(width * 0.52)
        if map_rendered_rect and style.text_position.startswith("bottom") and style.map_position.startswith("bottom"):
            # Jika peta dan teks sama-sama di bawah, sisakan ruang agar tidak tumpang tindih
            available_w = width - (map_rendered_rect[0] + map_rendered_rect[2]) - (margin * 2)
            if available_w > 200:
                max_text_block_width = available_w

        # Batas tinggi blok teks maksimal 35% tinggi foto per PRD
        max_allowed_height = int(height * 0.35)

        # Skala penyesuaian font jika teks melebihi tinggi maksimal 35%
        font_size = base_font_size
        font = load_font(style.font_name, font_size)
        wrapped_lines: list[str] = []

        for _ in range(5):  # Coba hingga 5 iterasi perkecil font jika perlu
            wrapped_lines = []
            for line in raw_lines:
                sub_lines = _wrap_text_line(line, max_text_block_width - 24, draw, font)
                wrapped_lines.extend(sub_lines)

            line_spacing = int(font_size * 0.35)
            # Hitung total tinggi teks
            total_text_h = 0
            for l in wrapped_lines:
                bbox = draw.textbbox((0, 0), l, font=font)
                total_text_h += (bbox[3] - bbox[1]) + line_spacing

            if total_text_h <= max_allowed_height or font_size <= 9:
                break
            # Perkecil font 15% jika terlalu panjang
            font_size = max(9, int(font_size * 0.85))
            font = load_font(style.font_name, font_size)

        # Hitung dimensi bounding box seluruh baris teks
        line_heights = []
        line_widths = []
        for l in wrapped_lines:
            bbox = draw.textbbox((0, 0), l, font=font)
            line_widths.append(bbox[2] - bbox[0])
            line_heights.append(bbox[3] - bbox[1])

        max_line_w = max(line_widths) if line_widths else 100
        line_spacing = int(font_size * 0.35)
        text_content_h = sum(line_heights) + line_spacing * max(0, len(wrapped_lines) - 1)

        padding_x = int(font_size * 0.8) if style.show_bg_box else 0
        padding_y = int(font_size * 0.6) if style.show_bg_box else 0
        box_w = max_line_w + (padding_x * 2)
        box_h = text_content_h + (padding_y * 2)

        # Tentukan posisi koordinat kotak teks
        align_right = True
        if style.text_position == "bottom_right":
            box_x = width - margin - box_w
            box_y = height - margin - box_h
            align_right = True
        elif style.text_position == "bottom_left":
            box_x = margin
            box_y = height - margin - box_h
            align_right = False
        elif style.text_position == "top_right":
            box_x = width - margin - box_w
            box_y = margin
            align_right = True
        elif style.text_position == "top_left":
            box_x = margin
            box_y = margin
            align_right = False
        else:
            box_x = width - margin - box_w
            box_y = height - margin - box_h
            align_right = True

        # Gambar Latar Belakang Semi-Transparan jika diaktifkan
        if style.show_bg_box:
            try:
                rgb_bg = ImageColor.getrgb(style.bg_box_color)
            except Exception:
                rgb_bg = (0, 0, 0)
            bg_rgba = (rgb_bg[0], rgb_bg[1], rgb_bg[2], style.bg_box_opacity)
            corner_r = max(4, int(font_size * 0.4))
            draw.rounded_rectangle(
                [box_x, box_y, box_x + box_w, box_y + box_h],
                radius=corner_r,
                fill=bg_rgba
            )

        # Warna Teks dan Outline
        try:
            rgb_text = ImageColor.getrgb(style.text_color)
            text_rgba = (rgb_text[0], rgb_text[1], rgb_text[2], 255)
        except Exception:
            text_rgba = (255, 255, 255, 255)

        try:
            rgb_out = ImageColor.getrgb(style.outline_color)
            out_rgba = (rgb_out[0], rgb_out[1], rgb_out[2], 220)
        except Exception:
            out_rgba = (0, 0, 0, 220)

        # Ketebalan outline proporsional agar teks tanpa border tetap sangat tajam & terbaca
        outline_dist = max(1, int(font_size * 0.055))

        # Gambar setiap baris teks
        cur_y = box_y + padding_y
        for idx, line in enumerate(wrapped_lines):
            lw = line_widths[idx]
            lh = line_heights[idx]

            if align_right:
                tx = (box_x + box_w) - padding_x - lw
            else:
                tx = box_x + padding_x

            # Bayangan / Outline tipis agar terbaca jelas di latar belakang foto apapun
            if style.text_outline:
                for ox in range(-outline_dist, outline_dist + 1):
                    for oy in range(-outline_dist, outline_dist + 1):
                        if ox != 0 or oy != 0:
                            draw.text((tx + ox, cur_y + oy), line, fill=out_rgba, font=font)

            draw.text((tx, cur_y), line, fill=text_rgba, font=font)
            cur_y += lh + line_spacing

    # Gabungkan layer overlay di atas foto asli
    final_img = Image.alpha_composite(base_img, overlay_layer)
    return final_img.convert("RGB")
