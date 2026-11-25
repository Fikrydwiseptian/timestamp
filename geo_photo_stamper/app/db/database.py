"""
Modul database SQLite untuk Geo Photo Stamper.
Menyimpan cache geocoding, preset gaya overlay, riwayat batch run, dan pengaturan aplikasi.
"""

from __future__ import annotations
import sqlite3
import json
from datetime import datetime
from typing import Any
from pathlib import Path
from app.utils.paths import get_db_path
from app.utils.logger import get_logger

logger = get_logger("Database")


class Database:
    """Pengelola koneksi dan query SQLite untuk aplikasi Geo Photo Stamper."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else get_db_path()
        self.init_database()

    def get_connection(self) -> sqlite3.Connection:
        """Membuka koneksi baru ke database dengan format baris dict (sqlite3.Row)."""
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_database(self) -> None:
        """Membuat tabel-tabel utama jika belum ada."""
        logger.info(f"Menginisialisasi database pada: {self.db_path}")
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Tabel Cache Geocoding
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS geocode_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lat_key REAL NOT NULL,
                    lon_key REAL NOT NULL,
                    street TEXT,
                    district TEXT,
                    regency TEXT,
                    province TEXT,
                    raw_display_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(lat_key, lon_key)
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_geocode_coords ON geocode_cache(lat_key, lon_key);")

            # 2. Tabel Presets
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS presets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    config_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 3. Tabel Batch Runs (Riwayat Eksekusi)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS batch_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    finished_at TIMESTAMP,
                    total INTEGER DEFAULT 0,
                    success INTEGER DEFAULT 0,
                    failed INTEGER DEFAULT 0,
                    output_dir TEXT
                );
            """)

            # 4. Tabel Batch Items (Detail per Foto dalam Batch)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS batch_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT,
                    printed_json TEXT,
                    sources_json TEXT,
                    FOREIGN KEY(run_id) REFERENCES batch_runs(id) ON DELETE CASCADE
                );
            """)

            # 5. Tabel Settings (Pengaturan Key-Value)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)
            conn.commit()

    # ==========================================
    # CRUD: Geocode Cache
    # ==========================================
    @staticmethod
    def coord_key(val: float) -> float:
        """Membulatkan koordinat ke 5 desimal (~1 meter presisi) untuk kunci cache."""
        return round(float(val), 5)

    def get_cached_geocode(self, lat: float, lon: float) -> dict[str, Any] | None:
        """Mencari cache geocoding berdasarkan koordinat."""
        lat_k = self.coord_key(lat)
        lon_k = self.coord_key(lon)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM geocode_cache WHERE lat_key = ? AND lon_key = ?",
                (lat_k, lon_k)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def save_geocode_cache(
        self,
        lat: float,
        lon: float,
        street: str,
        district: str,
        regency: str,
        province: str,
        raw_display_name: str = ""
    ) -> None:
        """Menyimpan atau memperbarui data alamat ke cache."""
        lat_k = self.coord_key(lat)
        lon_k = self.coord_key(lon)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO geocode_cache (lat_key, lon_key, street, district, regency, province, raw_display_name)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(lat_key, lon_key) DO UPDATE SET
                    street = excluded.street,
                    district = excluded.district,
                    regency = excluded.regency,
                    province = excluded.province,
                    raw_display_name = excluded.raw_display_name;
            """, (lat_k, lon_k, street, district, regency, province, raw_display_name))
            conn.commit()

    # ==========================================
    # CRUD: Presets
    # ==========================================
    def get_all_presets(self) -> list[dict[str, Any]]:
        """Mengambil seluruh preset gaya overlay yang tersimpan."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, config_json, created_at FROM presets ORDER BY name ASC")
            return [dict(r) for r in cursor.fetchall()]

    def get_preset_by_name(self, name: str) -> dict[str, Any] | None:
        """Mengambil preset berdasarkan nama."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM presets WHERE name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def save_preset(self, name: str, config: dict[str, Any] | str) -> None:
        """Menyimpan atau menimpa preset gaya overlay."""
        config_str = config if isinstance(config, str) else json.dumps(config, ensure_ascii=False)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO presets (name, config_json)
                VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET config_json = excluded.config_json;
            """, (name, config_str))
            conn.commit()

    def delete_preset(self, name: str) -> bool:
        """Menghapus preset berdasarkan nama."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM presets WHERE name = ?", (name,))
            conn.commit()
            return cursor.rowcount > 0

    # ==========================================
    # CRUD: Batch Runs & Items
    # ==========================================
    def create_batch_run(self, total: int, output_dir: str) -> int:
        """Membuat rekaman batch run baru dan mengembalikan ID run."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO batch_runs (total, output_dir) VALUES (?, ?)",
                (total, str(output_dir))
            )
            conn.commit()
            return int(cursor.lastrowid)

    def finish_batch_run(self, run_id: int, success: int, failed: int) -> None:
        """Memperbarui status selesai suatu batch run."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE batch_runs SET finished_at = CURRENT_TIMESTAMP, success = ?, failed = ? WHERE id = ?",
                (success, failed, run_id)
            )
            conn.commit()

    def add_batch_item(
        self,
        run_id: int,
        filename: str,
        status: str,
        error: str = "",
        printed_data: dict[str, Any] | str = "{}",
        sources_data: dict[str, Any] | str = "{}"
    ) -> None:
        """Menambahkan entri hasil pemrosesan file dalam suatu batch."""
        p_str = printed_data if isinstance(printed_data, str) else json.dumps(printed_data, ensure_ascii=False)
        s_str = sources_data if isinstance(sources_data, str) else json.dumps(sources_data, ensure_ascii=False)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO batch_items (run_id, filename, status, error, printed_json, sources_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (run_id, filename, status, error, p_str, s_str))
            conn.commit()

    # ==========================================
    # CRUD: Settings
    # ==========================================
    def get_setting(self, key: str, default: str = "") -> str:
        """Mengambil nilai setting."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        """Menyimpan atau memperbarui nilai setting."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value;
            """, (key, str(value)))
            conn.commit()

    def get_all_settings(self) -> dict[str, str]:
        """Mengambil semua pengaturan sebagai dictionary."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM settings")
            return {row["key"]: row["value"] for row in cursor.fetchall()}
