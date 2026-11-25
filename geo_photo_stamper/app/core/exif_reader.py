"""
Modul pembacaan metadata EXIF dan representasi data foto.
Mengekstrak tanggal ambil, GPS (lat/lon), altitude, arah (heading), kecepatan,
dan melakukan koreksi orientasi gambar.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from PIL import Image, ImageOps
import piexif

# Registrasi dukungan HEIC jika pillow_heif tersedia
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

from app.utils.logger import get_logger

logger = get_logger("ExifReader")


@dataclass
class PhotoMeta:
    """Representasi metadata dan status satu foto."""
    file_path: str
    file_name: str
    
    # Metadata waktu
    date_time: str = ""
    date_time_source: str = "none"  # "exif", "file_modified", "manual"
    
    # Metadata GPS
    lat: float | None = None
    lon: float | None = None
    coords_source: str = "none"  # "exif", "manual", "none"
    
    # Metadata Sensor
    altitude: float | None = None
    altitude_source: str = "none"  # "exif", "manual", "none"
    heading: float | None = None  # 0 - 360 derajat
    heading_source: str = "none"  # "exif", "manual", "none"
    speed: float | None = None  # km/h
    speed_source: str = "default"  # "exif", "manual", "default"
    
    # Geocoding / Alamat
    street: str = ""
    district: str = ""
    regency: str = ""
    province: str = ""
    address_source: str = "none"  # "geocoding", "manual", "none"
    
    # Informasi Tambahan
    notes: str = ""
    notes_source: str = "manual"
    index_no: int = 1
    index_source: str = "otomatis"
    
    # Orientasi dan Ukuran
    orientation: int = 1
    width: int = 0
    height: int = 0
    
    # Status Pemrosesan
    status: str = "data_kurang"  # "siap", "data_kurang", "selesai", "gagal"
    error_message: str = ""
    
    # Nilai Asli EXIF untuk deteksi modifikasi manual
    original_exif: dict[str, Any] = field(default_factory=dict)
    is_modified_manually: bool = False

    def update_status(self) -> None:
        """Memperbarui status ketersediaan data foto."""
        if self.status in ("selesai", "gagal"):
            return
        
        # Dianggap siap jika minimal memiliki koordinat dan waktu
        if self.lat is not None and self.lon is not None and self.date_time:
            self.status = "siap"
        else:
            self.status = "data_kurang"

    def get_sources_dict(self) -> dict[str, str]:
        """Mengembalikan mapping sumber data untuk pencatatan log CSV/DB."""
        return {
            "date_time": self.date_time_source,
            "coordinates": self.coords_source,
            "altitude": self.altitude_source,
            "heading": self.heading_source,
            "speed": self.speed_source,
            "address": self.address_source,
            "notes": self.notes_source,
            "index_no": self.index_source
        }

    def get_printed_values_dict(self) -> dict[str, Any]:
        """Mengembalikan data nilai yang tercetak pada foto."""
        return {
            "file_name": self.file_name,
            "date_time": self.date_time,
            "lat": self.lat,
            "lon": self.lon,
            "altitude": f"{self.altitude:.1f}m" if self.altitude is not None else "-",
            "heading": f"{int(self.heading)}°" if self.heading is not None else "-",
            "speed": f"{self.speed:.1f}km/h" if self.speed is not None else "0.0km/h",
            "street": self.street,
            "district": self.district,
            "regency": self.regency,
            "province": self.province,
            "notes": self.notes,
            "index_no": self.index_no
        }


def _convert_dms_to_decimal(dms_values: Any, ref: str) -> float | None:
    """Mengonversi koordinat EXIF DMS ((deg, den), (min, den), (sec, den)) ke desimal."""
    try:
        def to_float(val: Any) -> float:
            if isinstance(val, tuple) and len(val) == 2:
                num, den = val
                return float(num) / float(den) if den != 0 else 0.0
            return float(val)

        d = to_float(dms_values[0])
        m = to_float(dms_values[1])
        s = to_float(dms_values[2])
        dec = d + (m / 60.0) + (s / 3600.0)

        if ref.upper() in ["S", "W"]:
            dec = -dec
        return dec
    except Exception as e:
        logger.debug(f"Gagal parsing DMS koordinat: {e}")
        return None


def _parse_rational(val: Any) -> float | None:
    """Mengonversi nilai rational EXIF tuple (num, den) menjadi float."""
    try:
        if isinstance(val, tuple) and len(val) == 2:
            num, den = val
            return float(num) / float(den) if den != 0 else 0.0
        return float(val)
    except Exception:
        return None


def read_photo_metadata(file_path: str | Path) -> PhotoMeta:
    """
    Membaca metadata foto dari path yang diberikan.
    Mengekstrak tanggal EXIF, GPS (lat/lon, alt, heading, speed), orientasi, dan resolusi.
    """
    path_obj = Path(file_path)
    meta = PhotoMeta(
        file_path=str(path_obj.resolve()),
        file_name=path_obj.name
    )

    try:
        with Image.open(path_obj) as img:
            meta.width, meta.height = img.size
            
            # Cek orientasi awal
            exif_dict = {}
            try:
                raw_exif = img.info.get("exif")
                if raw_exif:
                    exif_dict = piexif.load(raw_exif)
            except Exception as e:
                logger.debug(f"Piexif load error pada {path_obj.name}: {e}")

            # 1. Orientasi
            orientation = 1
            if "0th" in exif_dict and piexif.ImageIFD.Orientation in exif_dict["0th"]:
                orientation = exif_dict["0th"][piexif.ImageIFD.Orientation]
            meta.orientation = orientation

            # 2. Tanggal dan Jam Ambil
            date_time_str = ""
            if "Exif" in exif_dict:
                for tag in (piexif.ExifIFD.DateTimeOriginal, piexif.ExifIFD.DateTimeDigitized):
                    if tag in exif_dict["Exif"]:
                        raw_dt = exif_dict["Exif"][tag]
                        if isinstance(raw_dt, bytes):
                            raw_dt = raw_dt.decode("utf-8", errors="ignore")
                        date_time_str = str(raw_dt).strip()
                        if date_time_str:
                            break

            if not date_time_str and "0th" in exif_dict and piexif.ImageIFD.DateTime in exif_dict["0th"]:
                raw_dt = exif_dict["0th"][piexif.ImageIFD.DateTime]
                if isinstance(raw_dt, bytes):
                    raw_dt = raw_dt.decode("utf-8", errors="ignore")
                date_time_str = str(raw_dt).strip()

            if date_time_str:
                # Format standar EXIF: YYYY:MM:DD HH:MM:SS
                try:
                    dt = datetime.strptime(date_time_str, "%Y:%m:%d %H:%M:%S")
                    meta.date_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    meta.date_time_source = "exif"
                except Exception:
                    meta.date_time = date_time_str
                    meta.date_time_source = "exif"
            else:
                # Fallback: Waktu modifikasi file
                mtime = os.path.getmtime(path_obj)
                dt = datetime.fromtimestamp(mtime)
                meta.date_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                meta.date_time_source = "file_modified"

            # 3. GPS Metadata
            if "GPS" in exif_dict and exif_dict["GPS"]:
                gps = exif_dict["GPS"]
                
                # Koordinat Latitude & Longitude
                lat_raw = gps.get(piexif.GPSIFD.GPSLatitude)
                lat_ref = gps.get(piexif.GPSIFD.GPSLatitudeRef, b"N")
                lon_raw = gps.get(piexif.GPSIFD.GPSLongitude)
                lon_ref = gps.get(piexif.GPSIFD.GPSLongitudeRef, b"E")

                if lat_raw and lon_raw:
                    lat_ref_str = lat_ref.decode("utf-8") if isinstance(lat_ref, bytes) else str(lat_ref)
                    lon_ref_str = lon_ref.decode("utf-8") if isinstance(lon_ref, bytes) else str(lon_ref)
                    lat = _convert_dms_to_decimal(lat_raw, lat_ref_str)
                    lon = _convert_dms_to_decimal(lon_raw, lon_ref_str)
                    if lat is not None and lon is not None:
                        meta.lat = round(lat, 6)
                        meta.lon = round(lon, 6)
                        meta.coords_source = "exif"

                # Ketinggian (Altitude)
                alt_raw = gps.get(piexif.GPSIFD.GPSAltitude)
                alt_ref = gps.get(piexif.GPSIFD.GPSAltitudeRef, 0)
                if alt_raw:
                    alt = _parse_rational(alt_raw)
                    if alt is not None:
                        # Ref 1 berarti di bawah permukaan laut
                        if alt_ref == 1:
                            alt = -alt
                        meta.altitude = round(alt, 1)
                        meta.altitude_source = "exif"

                # Arah Kompas (GPSImgDirection)
                heading_raw = gps.get(piexif.GPSIFD.GPSImgDirection)
                if heading_raw:
                    heading = _parse_rational(heading_raw)
                    if heading is not None:
                        meta.heading = round(heading % 360, 1)
                        meta.heading_source = "exif"

                # Kecepatan (GPSSpeed)
                speed_raw = gps.get(piexif.GPSIFD.GPSSpeed)
                speed_ref = gps.get(piexif.GPSIFD.GPSSpeedRef, b"K")
                if speed_raw:
                    speed = _parse_rational(speed_raw)
                    if speed is not None:
                        speed_ref_str = speed_ref.decode("utf-8") if isinstance(speed_ref, bytes) else str(speed_ref)
                        if speed_ref_str.upper() == "M":  # Mil/jam ke km/jam
                            speed *= 1.60934
                        elif speed_ref_str.upper() == "N":  # Knot ke km/jam
                            speed *= 1.852
                        meta.speed = round(speed, 1)
                        meta.speed_source = "exif"
                else:
                    meta.speed = 0.0
                    meta.speed_source = "default"
            else:
                meta.speed = 0.0
                meta.speed_source = "default"

    except Exception as e:
        logger.error(f"Error membaca foto {path_obj.name}: {e}")
        meta.status = "gagal"
        meta.error_message = str(e)
        return meta

    # Simpan snapshot EXIF asli untuk audit trail & deteksi modifikasi manual
    meta.original_exif = {
        "date_time": meta.date_time,
        "date_time_source": meta.date_time_source,
        "lat": meta.lat,
        "lon": meta.lon,
        "altitude": meta.altitude,
        "heading": meta.heading,
        "speed": meta.speed
    }

    meta.update_status()
    return meta


def load_and_orient_image(file_path: str | Path) -> Image.Image:
    """
    Membuka file gambar dan melakukan transposisi orientasi EXIF (ImageOps.exif_transpose)
    sehingga orientasi gambar selalu tegak lurus (upright) sebelum diproses.
    """
    img = Image.open(file_path)
    # Konversi RGBA jika palet, pastikan format RGB/RGBA didukung
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    try:
        transposed = ImageOps.exif_transpose(img)
        if transposed is not None:
            return transposed
    except Exception as e:
        logger.debug(f"exif_transpose gagal pada {file_path}: {e}")
    return img
