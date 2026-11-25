"""
Modul pemrosesan batch stempel foto (Geo Photo Stamper).
Menggunakan ThreadPoolExecutor untuk eksekusi paralel yang cepat dan aman,
progress callback ke UI, pembatalan aman, preservasi EXIF asli, pencegahan penimpaan file,
serta pencatatan log lengkap ke SQLite dan file CSV audit trail.
"""

from __future__ import annotations
import os
import csv
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Any
from PIL import Image
import piexif

from app.core.exif_reader import PhotoMeta, load_and_orient_image
from app.core.presets import OverlayStyle
from app.core.overlay import render_overlay
from app.db.database import Database
from app.utils.logger import get_logger

logger = get_logger("BatchProcessor")


def get_file_sha256(filepath: str | Path) -> str:
    """Menghitung hash SHA-256 untuk memvalidasi integritas file foto asli."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_unique_output_path(output_dir: Path, original_filename: str, suffix: str = "_stamped") -> Path:
    """
    Menghasilkan path output yang unik agar tidak menimpa file yang sudah ada.
    Contoh: foto.jpg -> foto_stamped.jpg atau foto_stamped_1.jpg.
    """
    p = Path(original_filename)
    stem = p.stem
    ext = p.suffix if p.suffix.lower() in [".jpg", ".jpeg", ".png"] else ".jpg"

    candidate = output_dir / f"{stem}{suffix}{ext}"
    if not candidate.exists():
        return candidate

    counter = 1
    while True:
        candidate = output_dir / f"{stem}{suffix}_{counter}{ext}"
        if not candidate.exists():
            return candidate
        counter += 1


class BatchProcessor:
    """Pengelola proses stempel batch untuk banyak foto."""

    def __init__(
        self,
        db: Database | None = None,
        max_workers: int = 4
    ) -> None:
        self.db = db if db is not None else Database()
        self.max_workers = max_workers
        self._cancel_event = threading.Event()
        self._is_running = False

    def cancel(self) -> None:
        """Mengirim sinyal pembatalan proses batch yang sedang berjalan."""
        logger.info("Menerima permintaan pembatalan batch.")
        self._cancel_event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def process_photos(
        self,
        photos: list[PhotoMeta],
        style: OverlayStyle,
        output_dir: str | Path,
        file_suffix: str = "_stamped",
        jpeg_quality: int = 92,
        on_progress: Callable[[int, int, str, str], None] | None = None,
        on_complete: Callable[[dict[str, Any]], None] | None = None
    ) -> dict[str, Any]:
        """
        Menjalankan proses batch penempelan overlay ke seluruh daftar foto.
        - Foto asli dipastikan tidak berubah (validasi SHA256).
        - Rekaman dicatat ke tabel batch_runs & batch_items di SQLite.
        - Log lengkap diekspor ke file CSV di folder output.
        """
        self._cancel_event.clear()
        self._is_running = True

        out_path_dir = Path(output_dir)
        out_path_dir.mkdir(parents=True, exist_ok=True)

        total_photos = len(photos)
        run_id = self.db.create_batch_run(total=total_photos, output_dir=str(out_path_dir))
        logger.info(f"Memulai Batch Run #{run_id} untuk {total_photos} foto ke {out_path_dir}")

        success_count = 0
        failed_count = 0
        processed_count = 0
        results_summary: list[dict[str, Any]] = []

        # Jalankan pemrosesan dengan thread pool
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_photo = {}
            for photo in photos:
                if self._cancel_event.is_set():
                    break
                fut = executor.submit(
                    self._process_single_photo,
                    photo,
                    style,
                    out_path_dir,
                    file_suffix,
                    jpeg_quality
                )
                future_to_photo[fut] = photo

            for future in as_completed(future_to_photo):
                photo_item = future_to_photo[future]
                processed_count += 1
                try:
                    res = future.result()
                    results_summary.append(res)
                    if res["status"] == "BERHASIL":
                        success_count += 1
                    else:
                        failed_count += 1

                    # Catat item ke database
                    self.db.add_batch_item(
                        run_id=run_id,
                        filename=photo_item.file_name,
                        status=res["status"],
                        error=res.get("error", ""),
                        printed_data=res.get("printed_values", {}),
                        sources_data=photo_item.get_sources_dict()
                    )

                    if on_progress:
                        on_progress(processed_count, total_photos, photo_item.file_name, res["status"])

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Gagal memproses file {photo_item.file_name}: {e}")
                    results_summary.append({
                        "filename": photo_item.file_name,
                        "status": "GAGAL",
                        "error": str(e),
                        "output_path": ""
                    })
                    if on_progress:
                        on_progress(processed_count, total_photos, photo_item.file_name, "GAGAL")

                if self._cancel_event.is_set():
                    logger.warning("Batch dihentikan oleh pengguna.")
                    break

        # Selesaikan rekaman batch run
        self.db.finish_batch_run(run_id, success=success_count, failed=failed_count)

        # Buat file CSV Audit Trail di folder output
        csv_path = out_path_dir / f"batch_log_run_{run_id}.csv"
        self._write_audit_csv(csv_path, results_summary)

        self._is_running = False

        final_summary = {
            "run_id": run_id,
            "total": total_photos,
            "success": success_count,
            "failed": failed_count,
            "cancelled": self._cancel_event.is_set(),
            "output_dir": str(out_path_dir),
            "csv_log": str(csv_path),
            "details": results_summary
        }

        if on_complete:
            on_complete(final_summary)

        return final_summary

    def _process_single_photo(
        self,
        meta: PhotoMeta,
        style: OverlayStyle,
        output_dir: Path,
        suffix: str,
        quality: int
    ) -> dict[str, Any]:
        """Memproses satu file foto dengan aman."""
        if self._cancel_event.is_set():
            return {
                "filename": meta.file_name,
                "status": "DIBATALKAN",
                "error": "Dibatalkan oleh pengguna",
                "output_path": ""
            }

        input_path = Path(meta.file_path)
        if not input_path.exists():
            return {
                "filename": meta.file_name,
                "status": "GAGAL",
                "error": "File asli tidak ditemukan",
                "output_path": ""
            }

        # Simpan hash sebelum diproses untuk verifikasi integritas
        original_sha = get_file_sha256(input_path)

        try:
            # 1. Buka dan orientasikan foto secara tegak lurus
            oriented_img = load_and_orient_image(input_path)

            # 2. Render overlay stempel
            stamped_img = render_overlay(oriented_img, meta, style)

            # 3. Tentukan nama output unik
            dest_path = get_unique_output_path(output_dir, meta.file_name, suffix)

            # 4. Ambil raw EXIF asli dari file sumber jika ada untuk dipertahankan
            raw_exif_bytes = None
            try:
                raw_exif_dict = piexif.load(str(input_path))
                # Reset tag orientasi ke 1 (Normal) karena gambar sudah dirotasi tegak
                if "0th" in raw_exif_dict and piexif.ImageIFD.Orientation in raw_exif_dict["0th"]:
                    raw_exif_dict["0th"][piexif.ImageIFD.Orientation] = 1
                raw_exif_bytes = piexif.dump(raw_exif_dict)
            except Exception as e:
                logger.debug(f"Piexif load/dump dilewati untuk {meta.file_name}: {e}")

            # 5. Simpan gambar hasil stempel
            if raw_exif_bytes:
                stamped_img.save(dest_path, format="JPEG", quality=quality, exif=raw_exif_bytes)
            else:
                stamped_img.save(dest_path, format="JPEG", quality=quality)

            # 6. Verifikasi ulang hash file asli TIDAK BERUBAH
            after_sha = get_file_sha256(input_path)
            if original_sha != after_sha:
                logger.critical(f"BAHAYA: Hash file asli {meta.file_name} berubah! Integritas terganggu!")
                raise RuntimeError("File asli termodifikasi saat pemrosesan!")

            meta.status = "selesai"
            return {
                "filename": meta.file_name,
                "status": "BERHASIL",
                "error": "",
                "output_path": str(dest_path),
                "printed_values": meta.get_printed_values_dict(),
                "sources": meta.get_sources_dict()
            }

        except Exception as e:
            logger.error(f"Gagal memproses overlay {meta.file_name}: {e}")
            meta.status = "gagal"
            meta.error_message = str(e)
            return {
                "filename": meta.file_name,
                "status": "GAGAL",
                "error": str(e),
                "output_path": ""
            }

    def _write_audit_csv(self, csv_path: Path, results: list[dict[str, Any]]) -> None:
        """Menulis audit trail lengkap ke format CSV."""
        fieldnames = [
            "Nama File",
            "Status",
            "Pesan Error",
            "Path Hasil",
            "Tanggal Tercetak",
            "Sumber Waktu",
            "GPS Lat",
            "GPS Lon",
            "Sumber GPS",
            "Ketinggian",
            "Sumber Ketinggian",
            "Arah Heading",
            "Sumber Arah",
            "Kecepatan",
            "Sumber Kecepatan",
            "Jalan",
            "Kecamatan",
            "Kabupaten/Kota",
            "Provinsi",
            "Sumber Alamat",
            "Nomor Indeks",
            "Catatan"
        ]

        try:
            with open(csv_path, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for item in results:
                    p = item.get("printed_values", {})
                    s = item.get("sources", {})
                    writer.writerow({
                        "Nama File": item.get("filename", ""),
                        "Status": item.get("status", ""),
                        "Pesan Error": item.get("error", ""),
                        "Path Hasil": item.get("output_path", ""),
                        "Tanggal Tercetak": p.get("date_time", ""),
                        "Sumber Waktu": s.get("date_time", ""),
                        "GPS Lat": p.get("lat", ""),
                        "GPS Lon": p.get("lon", ""),
                        "Sumber GPS": s.get("coordinates", ""),
                        "Ketinggian": p.get("altitude", ""),
                        "Sumber Ketinggian": s.get("altitude", ""),
                        "Arah Heading": p.get("heading", ""),
                        "Sumber Arah": s.get("heading", ""),
                        "Kecepatan": p.get("speed", ""),
                        "Sumber Kecepatan": s.get("speed", ""),
                        "Jalan": p.get("street", ""),
                        "Kecamatan": p.get("district", ""),
                        "Kabupaten/Kota": p.get("regency", ""),
                        "Provinsi": p.get("province", ""),
                        "Sumber Alamat": s.get("address", ""),
                        "Nomor Indeks": p.get("index_no", ""),
                        "Catatan": p.get("notes", "")
                    })
            logger.info(f"Audit log CSV berhasil ditulis: {csv_path}")
        except Exception as e:
            logger.error(f"Gagal menulis CSV audit log: {e}")
