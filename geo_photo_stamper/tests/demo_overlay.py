"""
Skrip pengujian demo penggambaran overlay Geo Photo Stamper.
Membuat gambar contoh dengan data tiruan dan menghasilkan output stempel foto.
"""

from pathlib import Path
import sys

# Tambahkan root folder ke sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from PIL import Image, ImageDraw
from app.core.exif_reader import PhotoMeta
from app.core.presets import get_default_style
from app.core.overlay import render_overlay


def create_sample_photo(width: int = 1920, height: int = 1080) -> Image.Image:
    """Membuat gambar sample gradien menyerupai foto pemandangan lapangan."""
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    # Langit ke Tanah (Gradien Biru ke Hijau Tanah)
    for y in range(height):
        ratio = y / height
        if ratio < 0.55:
            # Langit
            r = int(56 + (140 - 56) * (ratio / 0.55))
            g = int(189 + (210 - 189) * (ratio / 0.55))
            b = int(248 + (255 - 248) * (ratio / 0.55))
        else:
            # Bukit / Lapangan
            sub_r = (ratio - 0.55) / 0.45
            r = int(34 + (74 - 34) * sub_r)
            g = int(197 + (120 - 197) * sub_r)
            b = int(94 + (50 - 94) * sub_r)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Teks label watermarked
    draw.text((width // 2 - 150, height // 2 - 20), "FOTO DOKUMENTASI LAPANGAN", fill=(255, 255, 255, 120))
    return img


def main():
    print("Mempersiapkan pengujian demo overlay Geo Photo Stamper...")
    test_img = create_sample_photo(1920, 1080)

    # Data meta sampel sesuai contoh di PRD
    meta = PhotoMeta(
        file_path="sample_lapangan.jpg",
        file_name="sample_lapangan.jpg",
        date_time="2026-10-29 14:09:07",
        date_time_source="exif",
        lat=-8.12345,
        lon=113.67890,
        coords_source="exif",
        altitude=234.2,
        altitude_source="exif",
        heading=286.0,
        heading_source="exif",
        speed=0.0,
        speed_source="default",
        street="Jalan Tanpa Nama",
        district="Kecamatan Arjasa",
        regency="Kabupaten Jember",
        province="Jawa Timur",
        address_source="geocoding",
        notes="Inspeksi Wilayah Sucofindo",
        index_no=47
    )

    style = get_default_style()
    output_img = render_overlay(test_img, meta, style)

    out_path = Path(__file__).parent / "demo_stamped_output.jpg"
    output_img.save(out_path, format="JPEG", quality=92)
    print(f"Berhasil! Gambar demo tersimpan di: {out_path.resolve()}")


if __name__ == "__main__":
    main()
