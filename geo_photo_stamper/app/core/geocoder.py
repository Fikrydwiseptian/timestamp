"""
Modul Reverse Geocoding dan Forward Geocoding via OpenStreetMap Nominatim (geopy).
Dilengkapi rate limiter (1 req/detik), retry backoff, cache SQLite terintegrasi,
dan pemetaan komponen alamat standar Indonesia (Jalan, Kecamatan, Kabupaten/Kota, Provinsi).
"""

from __future__ import annotations
import time
import threading
from typing import Any
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable

from app.db.database import Database
from app.utils.logger import get_logger

logger = get_logger("Geocoder")


class GeocoderService:
    """Layanan Geocoding Nominatim dengan rate limit dan cache SQLite."""

    def __init__(self, db: Database | None = None) -> None:
        self.db = db if db is not None else Database()
        self.user_agent = "GeoPhotoStamper/1.0 (Sucofindo Desktop Tool; Windows)"
        self._geolocator = Nominatim(
            user_agent=self.user_agent,
            timeout=8
        )
        self._lock = threading.Lock()
        self._last_request_time: float = 0.0
        self.min_interval: float = 1.05  # Batas aman > 1 detik per permintaan

    def _wait_for_rate_limit(self) -> None:
        """Memastikan jeda minimal 1 detik antar permintaan ke server Nominatim."""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self._last_request_time = time.time()

    def reverse_geocode(
        self,
        lat: float,
        lon: float,
        use_online: bool = True
    ) -> dict[str, str]:
        """
        Mengambil alamat berdasarkan koordinat latitude & longitude.
        Memeriksa cache SQLite terlebih dahulu.
        Jika tidak ada di cache dan use_online=True, memanggil API Nominatim.
        """
        # 1. Cek Cache Lokal
        cached = self.db.get_cached_geocode(lat, lon)
        if cached:
            logger.debug(f"Cache hit untuk koordinat ({lat:.5f}, {lon:.5f})")
            return {
                "street": cached["street"] or "Jalan Tanpa Nama",
                "district": cached["district"] or "-",
                "regency": cached["regency"] or "-",
                "province": cached["province"] or "-",
                "display_name": cached["raw_display_name"] or "",
                "source": "geocoding_cache"
            }

        # Jika offline atau online dinonaktifkan
        if not use_online:
            return {
                "street": "Jalan Tanpa Nama",
                "district": "Alamat belum tersedia (offline)",
                "regency": "-",
                "province": "-",
                "display_name": "",
                "source": "offline"
            }

        # 2. Panggilan Online dengan Retry
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                self._wait_for_rate_limit()
                logger.info(f"Meminta geocode online untuk ({lat:.5f}, {lon:.5f}) [Percobaan {attempt + 1}]")
                location = self._geolocator.reverse(
                    (lat, lon),
                    language="id",
                    addressdetails=True
                )
                if not location or not location.raw:
                    break

                raw_addr: dict[str, Any] = location.raw.get("address", {})
                display_name: str = location.address or ""

                # Ekstraksi Nama Jalan
                street = (
                    raw_addr.get("road")
                    or raw_addr.get("pedestrian")
                    or raw_addr.get("street")
                    or raw_addr.get("residential")
                    or raw_addr.get("footway")
                    or raw_addr.get("path")
                    or "Jalan Tanpa Nama"
                )

                # Ekstraksi Kecamatan / Sub-district
                district = (
                    raw_addr.get("subdistrict")
                    or raw_addr.get("city_district")
                    or raw_addr.get("suburb")
                    or raw_addr.get("town")
                    or raw_addr.get("village")
                    or raw_addr.get("municipality")
                    or "-"
                )
                if district != "-" and not district.lower().startswith("kecamatan") and not district.lower().startswith("kelurahan"):
                    district = f"Kecamatan {district}"

                # Ekstraksi Kabupaten / Kota
                regency = (
                    raw_addr.get("city")
                    or raw_addr.get("county")
                    or raw_addr.get("regency")
                    or raw_addr.get("state_district")
                    or "-"
                )

                # Ekstraksi Provinsi
                province = (
                    raw_addr.get("state")
                    or raw_addr.get("province")
                    or raw_addr.get("region")
                    or "-"
                )

                # Simpan ke Cache
                self.db.save_geocode_cache(
                    lat=lat,
                    lon=lon,
                    street=street,
                    district=district,
                    regency=regency,
                    province=province,
                    raw_display_name=display_name
                )

                return {
                    "street": street,
                    "district": district,
                    "regency": regency,
                    "province": province,
                    "display_name": display_name,
                    "source": "geocoding_online"
                }

            except (GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable) as e:
                logger.warning(f"Nominatim timeout/error (percobaan {attempt + 1}/{max_retries + 1}): {e}")
                time.sleep(1.0 * (attempt + 1))
            except Exception as e:
                logger.error(f"Error tak terduga saat geocoding ({lat}, {lon}): {e}")
                break

        # Fallback bila jaringan gagal
        return {
            "street": "Jalan Tanpa Nama",
            "district": "Alamat belum tersedia",
            "regency": "-",
            "province": "-",
            "display_name": "",
            "source": "failed"
        }

    def search_place(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Pencarian tempat (Forward Geocoding) berdasarkan nama jalan, kota, atau landmark.
        Mengembalikan daftar hasil koordinat dan nama lengkap.
        """
        if not query or not query.strip():
            return []

        try:
            self._wait_for_rate_limit()
            logger.info(f"Mencari lokasi: '{query}'")
            results = self._geolocator.geocode(
                query.strip(),
                language="id",
                addressdetails=True,
                exactly_one=False,
                limit=limit
            )
            if not results:
                return []

            out = []
            for item in results:
                raw_addr: dict[str, Any] = item.raw.get("address", {})
                street = (
                    raw_addr.get("road")
                    or raw_addr.get("pedestrian")
                    or raw_addr.get("residential")
                    or raw_addr.get("suburb")
                    or "Jalan Tanpa Nama"
                )
                district = raw_addr.get("city_district") or raw_addr.get("subdistrict") or raw_addr.get("suburb") or "-"
                regency = raw_addr.get("city") or raw_addr.get("county") or raw_addr.get("regency") or "-"
                province = raw_addr.get("state") or "-"

                out.append({
                    "display_name": item.address,
                    "lat": float(item.latitude),
                    "lon": float(item.longitude),
                    "street": street,
                    "district": district,
                    "regency": regency,
                    "province": province
                })
            return out
        except Exception as e:
            logger.warning(f"Pencarian tempat gagal untuk '{query}': {e}")
            return []
