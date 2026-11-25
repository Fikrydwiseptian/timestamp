"""
Modal dialog penyuntingan data metadata foto secara manual dan pencarian lokasi online.
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from typing import Callable, Any

from app.core.exif_reader import PhotoMeta
from app.core.geocoder import GeocoderService
from app.utils.logger import get_logger

logger = get_logger("EditModal")


class EditPhotoModal(ctk.CTkToplevel):
    """Jendela modal penyuntingan metadata dan lokasi foto."""

    def __init__(
        self,
        parent: Any,
        photo: PhotoMeta,
        geocoder: GeocoderService,
        on_save: Callable[[PhotoMeta], None]
    ) -> None:
        super().__init__(parent)
        self.photo = photo
        self.geocoder = geocoder
        self.on_save = on_save

        self.title(f"Edit Data Foto - {photo.file_name}")
        self.geometry("640x740")
        self.minsize(560, 640)
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self._load_data()

    def _build_ui(self) -> None:
        """Membangun elemen UI form modal."""
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(15, 5))
        ctk.CTkLabel(
            header_frame,
            text="Sunting Informasi & Lokasi Foto",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w")
        ctk.CTkLabel(
            header_frame,
            text=f"File: {self.photo.file_name}",
            text_color="gray70",
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w")

        # Banner Peringatan EXIF
        self.warning_banner = ctk.CTkFrame(self, fg_color="#B45309", corner_radius=6)
        self.warning_label = ctk.CTkLabel(
            self.warning_banner,
            text="⚠️ PERINGATAN: Nilai waktu atau koordinat diubah manual dari data asli kamera.",
            text_color="white",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.warning_label.pack(padx=12, pady=6)
        # Sembunyikan default
        self.warning_banner.pack_forget()

        # Tab atau Scrollable Form
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=10)

        # ----------------------------------------------------
        # Bagian 1: Pencarian Tempat (Forward Geocoding)
        # ----------------------------------------------------
        search_box = ctk.CTkFrame(scroll, corner_radius=8)
        search_box.pack(fill="x", pady=(0, 15), padx=2)

        ctk.CTkLabel(search_box, text="Cari Tempat / Alamat Online (Nominatim)", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))
        
        search_row = ctk.CTkFrame(search_box, fg_color="transparent")
        search_row.pack(fill="x", padx=12, pady=(0, 8))
        self.search_entry = ctk.CTkEntry(search_row, placeholder_text="Ketik nama jalan, kantor, atau kota...")
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.search_btn = ctk.CTkButton(search_row, text="Cari", width=80, command=self._do_search_place)
        self.search_btn.pack(side="right")

        self.search_results_var = tk.StringVar(value="Hasil pencarian...")
        self.search_results_menu = ctk.CTkOptionMenu(
            search_box,
            values=["(Ketik pencarian di atas)"],
            command=self._on_select_search_result
        )
        self.search_results_menu.pack(fill="x", padx=12, pady=(0, 12))
        self._search_items_cache: list[dict[str, Any]] = []

        # ----------------------------------------------------
        # Bagian 2: Tanggal & Waktu
        # ----------------------------------------------------
        time_box = ctk.CTkFrame(scroll, corner_radius=8)
        time_box.pack(fill="x", pady=(0, 15), padx=2)
        ctk.CTkLabel(time_box, text="Waktu Dokumentasi", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(10, 6))

        t_row = ctk.CTkFrame(time_box, fg_color="transparent")
        t_row.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(t_row, text="Tanggal & Jam (YYYY-MM-DD HH:MM:SS):", width=220, anchor="w").pack(side="left")
        self.entry_datetime = ctk.CTkEntry(t_row)
        self.entry_datetime.pack(side="right", fill="x", expand=True)

        # ----------------------------------------------------
        # Bagian 3: Koordinat & Sensor
        # ----------------------------------------------------
        coord_box = ctk.CTkFrame(scroll, corner_radius=8)
        coord_box.pack(fill="x", pady=(0, 15), padx=2)
        ctk.CTkLabel(coord_box, text="Koordinat GPS & Sensor", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(10, 6))

        # Lat / Lon
        row_lat = ctk.CTkFrame(coord_box, fg_color="transparent")
        row_lat.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row_lat, text="Latitude (Desimal):", width=160, anchor="w").pack(side="left")
        self.entry_lat = ctk.CTkEntry(row_lat, placeholder_text="-8.12345")
        self.entry_lat.pack(side="right", fill="x", expand=True)

        row_lon = ctk.CTkFrame(coord_box, fg_color="transparent")
        row_lon.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row_lon, text="Longitude (Desimal):", width=160, anchor="w").pack(side="left")
        self.entry_lon = ctk.CTkEntry(row_lon, placeholder_text="113.67890")
        self.entry_lon.pack(side="right", fill="x", expand=True)

        # Reverse Geocode Button
        btn_rev = ctk.CTkButton(
            coord_box,
            text="📍 Ambil Alamat Otomatis dari Koordinat Ini",
            fg_color="#0284C7",
            hover_color="#0369A1",
            command=self._do_reverse_geocode_coords
        )
        btn_rev.pack(fill="x", padx=12, pady=(4, 10))

        # Altitude / Heading / Speed
        row_sensor = ctk.CTkFrame(coord_box, fg_color="transparent")
        row_sensor.pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkLabel(row_sensor, text="Alt (m):").pack(side="left", padx=(0, 4))
        self.entry_alt = ctk.CTkEntry(row_sensor, width=70)
        self.entry_alt.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(row_sensor, text="Arah (°):").pack(side="left", padx=(0, 4))
        self.entry_heading = ctk.CTkEntry(row_sensor, width=70)
        self.entry_heading.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(row_sensor, text="Kec (km/h):").pack(side="left", padx=(0, 4))
        self.entry_speed = ctk.CTkEntry(row_sensor, width=70)
        self.entry_speed.pack(side="left")

        # ----------------------------------------------------
        # Bagian 4: Alamat Terperinci
        # ----------------------------------------------------
        addr_box = ctk.CTkFrame(scroll, corner_radius=8)
        addr_box.pack(fill="x", pady=(0, 15), padx=2)
        ctk.CTkLabel(addr_box, text="Komponen Alamat Overlay", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(10, 6))

        for field_id, label_text in [
            ("street", "Nama Jalan:"),
            ("district", "Kecamatan / Kelurahan:"),
            ("regency", "Kabupaten / Kota:"),
            ("province", "Provinsi:")
        ]:
            r = ctk.CTkFrame(addr_box, fg_color="transparent")
            r.pack(fill="x", padx=12, pady=4)
            ctk.CTkLabel(r, text=label_text, width=160, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(r)
            entry.pack(side="right", fill="x", expand=True)
            setattr(self, f"entry_{field_id}", entry)

        # ----------------------------------------------------
        # Bagian 5: Catatan Tambahan
        # ----------------------------------------------------
        notes_box = ctk.CTkFrame(scroll, corner_radius=8)
        notes_box.pack(fill="x", pady=(0, 10), padx=2)
        ctk.CTkLabel(notes_box, text="Catatan Lapangan (Opsional):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))
        self.entry_notes = ctk.CTkEntry(notes_box, placeholder_text="Contoh: Inspeksi tiang trafo #12")
        self.entry_notes.pack(fill="x", padx=12, pady=(0, 12))

        # ----------------------------------------------------
        # Tombol Aksi Bawah
        # ----------------------------------------------------
        btn_bar = ctk.CTkFrame(self, fg_color="transparent")
        btn_bar.pack(fill="x", padx=20, pady=(10, 15))

        btn_cancel = ctk.CTkButton(btn_bar, text="Batal", fg_color="gray30", hover_color="gray40", command=self.destroy)
        btn_cancel.pack(side="right", padx=(8, 0))

        btn_save = ctk.CTkButton(
            btn_bar,
            text="Simpan Perubahan",
            fg_color="#10B981",
            hover_color="#059669",
            command=self._save_changes
        )
        btn_save.pack(side="right")

    def _load_data(self) -> None:
        """Memuat data foto saat ini ke dalam form input."""
        self.entry_datetime.insert(0, self.photo.date_time or "")
        self.entry_lat.insert(0, str(self.photo.lat) if self.photo.lat is not None else "")
        self.entry_lon.insert(0, str(self.photo.lon) if self.photo.lon is not None else "")
        self.entry_alt.insert(0, str(self.photo.altitude) if self.photo.altitude is not None else "")
        self.entry_heading.insert(0, str(self.photo.heading) if self.photo.heading is not None else "")
        self.entry_speed.insert(0, str(self.photo.speed) if self.photo.speed is not None else "0.0")

        self.entry_street.insert(0, self.photo.street or "")
        self.entry_district.insert(0, self.photo.district or "")
        self.entry_regency.insert(0, self.photo.regency or "")
        self.entry_province.insert(0, self.photo.province or "")
        self.entry_notes.insert(0, self.photo.notes or "")

        self._check_warning()

    def _check_warning(self) -> None:
        """Menampilkan banner peringatan jika nilai waktu atau GPS berubah dari EXIF asli."""
        orig = self.photo.original_exif
        if not orig:
            return

        cur_dt = self.entry_datetime.get().strip()
        cur_lat = self.entry_lat.get().strip()
        cur_lon = self.entry_lon.get().strip()

        orig_dt = str(orig.get("date_time", "") or "")
        orig_lat = str(orig.get("lat", "") or "")
        orig_lon = str(orig.get("lon", "") or "")

        is_different = False
        if orig_dt and cur_dt != orig_dt:
            is_different = True
        if orig_lat and cur_lat != orig_lat:
            is_different = True
        if orig_lon and cur_lon != orig_lon:
            is_different = True

        if is_different:
            self.warning_banner.pack(fill="x", padx=20, pady=5)
        else:
            self.warning_banner.pack_forget()

    def _do_search_place(self) -> None:
        """Menjalankan forward geocoding berdasarkan kata kunci nama tempat."""
        query = self.search_entry.get().strip()
        if not query:
            return

        self.search_btn.configure(text="Mencari...", state="disabled")
        self.update_idletasks()

        results = self.geocoder.search_place(query, limit=6)
        self.search_btn.configure(text="Cari", state="normal")

        if not results:
            self.search_results_menu.configure(values=["Tidak ada hasil ditemukan"])
            return

        self._search_items_cache = results
        titles = [f"{r['display_name'][:75]}..." for r in results]
        self.search_results_menu.configure(values=titles)
        self.search_results_menu.set(titles[0])
        self._on_select_search_result(titles[0])

    def _on_select_search_result(self, selected_title: str) -> None:
        """Mengisi form otomatis ketika memilih salah satu hasil pencarian tempat."""
        for item in self._search_items_cache:
            if item["display_name"].startswith(selected_title[:40]):
                self.entry_lat.delete(0, "end")
                self.entry_lat.insert(0, f"{item['lat']:.6f}")

                self.entry_lon.delete(0, "end")
                self.entry_lon.insert(0, f"{item['lon']:.6f}")

                self.entry_street.delete(0, "end")
                self.entry_street.insert(0, item.get("street", "Jalan Tanpa Nama"))

                self.entry_district.delete(0, "end")
                self.entry_district.insert(0, item.get("district", "-"))

                self.entry_regency.delete(0, "end")
                self.entry_regency.insert(0, item.get("regency", "-"))

                self.entry_province.delete(0, "end")
                self.entry_province.insert(0, item.get("province", "-"))
                self._check_warning()
                break

    def _do_reverse_geocode_coords(self) -> None:
        """Memanggil reverse geocoding berdasarkan latitude dan longitude di entry."""
        try:
            lat = float(self.entry_lat.get().strip())
            lon = float(self.entry_lon.get().strip())
        except ValueError:
            return

        res = self.geocoder.reverse_geocode(lat, lon, use_online=True)
        self.entry_street.delete(0, "end")
        self.entry_street.insert(0, res.get("street", "Jalan Tanpa Nama"))

        self.entry_district.delete(0, "end")
        self.entry_district.insert(0, res.get("district", "-"))

        self.entry_regency.delete(0, "end")
        self.entry_regency.insert(0, res.get("regency", "-"))

        self.entry_province.delete(0, "end")
        self.entry_province.insert(0, res.get("province", "-"))
        self._check_warning()

    def _save_changes(self) -> None:
        """Menyimpan data dari form ke objek PhotoMeta."""
        self._check_warning()

        self.photo.date_time = self.entry_datetime.get().strip()
        self.photo.date_time_source = "manual"

        try:
            lat_val = self.entry_lat.get().strip()
            self.photo.lat = float(lat_val) if lat_val else None
            self.photo.coords_source = "manual"
        except ValueError:
            pass

        try:
            lon_val = self.entry_lon.get().strip()
            self.photo.lon = float(lon_val) if lon_val else None
        except ValueError:
            pass

        try:
            alt_val = self.entry_alt.get().strip()
            self.photo.altitude = float(alt_val) if alt_val else None
            self.photo.altitude_source = "manual"
        except ValueError:
            pass

        try:
            head_val = self.entry_heading.get().strip()
            self.photo.heading = float(head_val) if head_val else None
            self.photo.heading_source = "manual"
        except ValueError:
            pass

        try:
            spd_val = self.entry_speed.get().strip()
            self.photo.speed = float(spd_val) if spd_val else 0.0
            self.photo.speed_source = "manual"
        except ValueError:
            pass

        self.photo.street = self.entry_street.get().strip() or "Jalan Tanpa Nama"
        self.photo.district = self.entry_district.get().strip()
        self.photo.regency = self.entry_regency.get().strip()
        self.photo.province = self.entry_province.get().strip()
        self.photo.address_source = "manual"

        self.photo.notes = self.entry_notes.get().strip()
        self.photo.notes_source = "manual"

        self.photo.is_modified_manually = True
        self.photo.update_status()

        if self.on_save:
            self.on_save(self.photo)

        self.destroy()
