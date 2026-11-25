"""
Panel daftar foto (PhotoListPanel).
Menampilkan thumbnail, nama file, tanggal, koordinat, dan status data tiap foto.
Mendukung multi-seleksi, impor file/folder, drag-and-drop, dan eksekusi geocoding batch.
"""

from __future__ import annotations
import os
import threading
from pathlib import Path
from typing import Callable, Any
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image

from app.core.exif_reader import PhotoMeta, read_photo_metadata
from app.core.geocoder import GeocoderService
from app.utils.logger import get_logger

logger = get_logger("PhotoListUI")

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic"}


class PhotoItemCard(ctk.CTkFrame):
    """Kartu tampilan baris untuk satu item foto."""

    def __init__(
        self,
        parent: Any,
        meta: PhotoMeta,
        on_click: Callable[[PhotoMeta], None],
        on_double_click: Callable[[PhotoMeta], None],
        on_check_toggle: Callable[[PhotoMeta, bool], None]
    ) -> None:
        super().__init__(parent, corner_radius=6, fg_color="gray17")
        self.meta = meta
        self.on_click = on_click
        self.on_double_click = on_double_click
        self.on_check_toggle = on_check_toggle

        self.is_selected = False
        self._build_ui()

    def _build_ui(self) -> None:
        """Membuat komponen kartu foto."""
        # Checkbox seleksi
        self.check_var = tk.BooleanVar(value=False)
        self.chk = ctk.CTkCheckBox(
            self,
            text="",
            width=20,
            variable=self.check_var,
            command=self._on_check
        )
        self.chk.pack(side="left", padx=(8, 4))

        # Thumbnail Placeholder
        self.thumb_label = ctk.CTkLabel(self, text="🖼️", width=48, height=48, fg_color="gray25", corner_radius=4)
        self.thumb_label.pack(side="left", padx=4, pady=4)

        # Info Frame (Tengah)
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=8, pady=4)

        # Nama File
        self.lbl_name = ctk.CTkLabel(
            info_frame,
            text=self.meta.file_name,
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w"
        )
        self.lbl_name.pack(anchor="w")

        # Sub-info: Waktu & Koordinat
        coords_str = f"{self.meta.lat:.4f}, {self.meta.lon:.4f}" if (self.meta.lat is not None and self.meta.lon is not None) else "Tanpa GPS"
        time_str = self.meta.date_time if self.meta.date_time else "-"
        self.lbl_sub = ctk.CTkLabel(
            info_frame,
            text=f"{time_str} | {coords_str}",
            font=ctk.CTkFont(size=11),
            text_color="gray70",
            anchor="w"
        )
        self.lbl_sub.pack(anchor="w")

        # Status Badge (Kanan)
        self.badge = ctk.CTkLabel(
            self,
            text=self._status_text(),
            fg_color=self._status_color(),
            text_color="white",
            corner_radius=4,
            font=ctk.CTkFont(size=10, weight="bold"),
            width=80,
            height=24
        )
        self.badge.pack(side="right", padx=(4, 10))

        # Event Klik Kartu
        for widget in (self, info_frame, self.lbl_name, self.lbl_sub, self.thumb_label):
            widget.bind("<Button-1>", lambda e: self.on_click(self.meta))
            widget.bind("<Double-Button-1>", lambda e: self.on_double_click(self.meta))

    def _on_check(self) -> None:
        self.on_check_toggle(self.meta, self.check_var.get())

    def _status_text(self) -> str:
        s = self.meta.status
        if s == "siap":
            return "SIAP"
        elif s == "data_kurang":
            return "DATA KURANG"
        elif s == "selesai":
            return "SELESAI"
        elif s == "gagal":
            return "GAGAL"
        return s.upper()

    def _status_color(self) -> str:
        s = self.meta.status
        if s == "siap":
            return "#059669"  # Hijau Emerald
        elif s == "data_kurang":
            return "#D97706"  # Amber
        elif s == "selesai":
            return "#2563EB"  # Biru
        elif s == "gagal":
            return "#DC2626"  # Merah
        return "gray40"

    def update_data(self) -> None:
        """Memperbarui teks tampilan setelah metadata diedit."""
        coords_str = f"{self.meta.lat:.4f}, {self.meta.lon:.4f}" if (self.meta.lat is not None and self.meta.lon is not None) else "Tanpa GPS"
        time_str = self.meta.date_time if self.meta.date_time else "-"
        self.lbl_sub.configure(text=f"{time_str} | {coords_str}")
        self.badge.configure(text=self._status_text(), fg_color=self._status_color())

    def set_thumbnail(self, ctk_image: ctk.CTkImage) -> None:
        """Menyetel thumbnail setelah dibuat di thread background."""
        self.thumb_label.configure(image=ctk_image, text="")

    def set_active(self, active: bool) -> None:
        """Menyorot kartu jika sedang aktif dipilih untuk pratinjau."""
        self.configure(fg_color="#1E293B" if active else "gray17")


class PhotoListPanel(ctk.CTkFrame):
    """Panel daftar foto lengkap dengan kontrol aksi."""

    def __init__(
        self,
        parent: Any,
        geocoder: GeocoderService,
        on_select_photo: Callable[[PhotoMeta], None],
        on_edit_photo: Callable[[PhotoMeta], None]
    ) -> None:
        super().__init__(parent, corner_radius=10)
        self.geocoder = geocoder
        self.on_select_photo = on_select_photo
        self.on_edit_photo = on_edit_photo

        self.photos: list[PhotoMeta] = []
        self.card_widgets: dict[str, PhotoItemCard] = {}
        self.selected_set: set[str] = set()
        self.active_photo: PhotoMeta | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        """Membangun layout panel daftar foto."""
        # Header & Tombol Impor
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=12, pady=(12, 6))

        ctk.CTkLabel(
            top_bar,
            text="Daftar Foto Lapangan",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left")

        self.lbl_count = ctk.CTkLabel(
            top_bar,
            text="(0 foto)",
            font=ctk.CTkFont(size=12),
            text_color="gray70"
        )
        self.lbl_count.pack(side="left", padx=8)

        # Baris Tombol Tambah
        btn_row1 = ctk.CTkFrame(self, fg_color="transparent")
        btn_row1.pack(fill="x", padx=12, pady=(0, 6))

        btn_add_files = ctk.CTkButton(
            btn_row1,
            text="➕ Tambah Foto",
            command=self._on_add_files,
            width=110,
            fg_color="#3B82F6",
            hover_color="#2563EB"
        )
        btn_add_files.pack(side="left", padx=(0, 6), fill="x", expand=True)

        btn_add_folder = ctk.CTkButton(
            btn_row1,
            text="📁 Tambah Folder",
            command=self._on_add_folder,
            width=110,
            fg_color="#475569",
            hover_color="#334155"
        )
        btn_add_folder.pack(side="left", fill="x", expand=True)

        # Baris Aksi Batch
        btn_row2 = ctk.CTkFrame(self, fg_color="transparent")
        btn_row2.pack(fill="x", padx=12, pady=(0, 8))

        self.btn_geocode_all = ctk.CTkButton(
            btn_row2,
            text="🌐 Ambil Alamat Otomatis",
            font=ctk.CTkFont(size=11),
            height=28,
            fg_color="#0D9488",
            hover_color="#0F766E",
            command=self._do_batch_geocoding
        )
        self.btn_geocode_all.pack(side="left", padx=(0, 6), fill="x", expand=True)

        btn_del_sel = ctk.CTkButton(
            btn_row2,
            text="Hapus",
            font=ctk.CTkFont(size=11),
            height=28,
            width=65,
            fg_color="#7F1D1D",
            hover_color="#991B1B",
            command=self._delete_selected
        )
        btn_del_sel.pack(side="left")

        # Scrollable List Container
        self.scroll_list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_list.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Placeholder jika kosong
        self.empty_label = ctk.CTkLabel(
            self.scroll_list,
            text="Belum ada foto yang dipilih.\n\nKlik 'Tambah Foto' atau 'Tambah Folder'\nuntuk memulai dokumentasi.",
            text_color="gray60",
            font=ctk.CTkFont(size=13)
        )
        self.empty_label.pack(pady=60)

        # Bottom Bar: Seleksi Cepat
        bottom_bar = ctk.CTkFrame(self, fg_color="transparent")
        bottom_bar.pack(fill="x", padx=12, pady=(0, 10))

        btn_sel_all = ctk.CTkButton(
            bottom_bar,
            text="Pilih Semua",
            font=ctk.CTkFont(size=11),
            height=26,
            width=85,
            fg_color="gray30",
            hover_color="gray40",
            command=self._select_all
        )
        btn_sel_all.pack(side="left", padx=(0, 6))

        btn_unsel = ctk.CTkButton(
            bottom_bar,
            text="Batal Pilih",
            font=ctk.CTkFont(size=11),
            height=26,
            width=85,
            fg_color="gray30",
            hover_color="gray40",
            command=self._unselect_all
        )
        btn_unsel.pack(side="left", padx=(0, 6))

        self.btn_apply_loc = ctk.CTkButton(
            bottom_bar,
            text="Terapkan Lokasi ke Terpilih",
            font=ctk.CTkFont(size=11),
            height=26,
            fg_color="#6366F1",
            hover_color="#4F46E5",
            command=self._apply_location_to_selected
        )
        self.btn_apply_loc.pack(side="right")

    def _on_add_files(self) -> None:
        """Dialog memilih banyak file foto."""
        file_paths = filedialog.askopenfilenames(
            title="Pilih Foto Lapangan",
            filetypes=[
                ("File Foto", "*.jpg *.jpeg *.png *.heic"),
                ("Semua File", "*.*")
            ]
        )
        if file_paths:
            self.add_files_by_paths(file_paths)

    def _on_add_folder(self) -> None:
        """Dialog memilih seluruh folder foto."""
        folder = filedialog.askdirectory(title="Pilih Folder Foto")
        if folder:
            paths = []
            for root, _, files in os.walk(folder):
                for f in files:
                    if Path(f).suffix.lower() in SUPPORTED_EXTENSIONS:
                        paths.append(os.path.join(root, f))
            if paths:
                self.add_files_by_paths(paths)

    def add_files_by_paths(self, file_paths: list[str] | tuple[str, ...]) -> None:
        """Memproses impor daftar path file ke antrian."""
        existing_paths = {p.file_path for p in self.photos}
        new_items = []
        for fp in file_paths:
            resolved = str(Path(fp).resolve())
            if resolved not in existing_paths and Path(resolved).suffix.lower() in SUPPORTED_EXTENSIONS:
                existing_paths.add(resolved)
                meta = read_photo_metadata(resolved)
                new_items.append(meta)

        if not new_items:
            return

        self.photos.extend(new_items)
        self._refresh_list_view()

        # Otomatis pilih item pertama jika belum ada yang aktif
        if self.active_photo is None and self.photos:
            self._select_active(self.photos[0])

        # Buat thumbnail di thread terpisah agar UI tidak freeze
        threading.Thread(target=self._generate_thumbnails, args=(new_items,), daemon=True).start()

    def _refresh_list_view(self) -> None:
        """Merender ulang daftar kartu foto."""
        if not self.photos:
            self.empty_label.pack(pady=60)
            self.lbl_count.configure(text="(0 foto)")
            return

        self.empty_label.pack_forget()
        self.lbl_count.configure(text=f"({len(self.photos)} foto)")

        # Render kartu yang belum ada
        for meta in self.photos:
            if meta.file_path not in self.card_widgets:
                card = PhotoItemCard(
                    self.scroll_list,
                    meta=meta,
                    on_click=self._select_active,
                    on_double_click=self.on_edit_photo,
                    on_check_toggle=self._on_item_checked
                )
                card.pack(fill="x", pady=3, padx=2)
                self.card_widgets[meta.file_path] = card

    def _generate_thumbnails(self, items: list[PhotoMeta]) -> None:
        """Membuat thumbnail kecil di background."""
        for meta in items:
            try:
                with Image.open(meta.file_path) as img:
                    img.thumbnail((80, 80))
                    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(48, 48))
                    card = self.card_widgets.get(meta.file_path)
                    if card:
                        # Update di main thread
                        self.after(0, lambda c=card, i=ctk_img: c.set_thumbnail(i))
            except Exception as e:
                logger.debug(f"Gagal generate thumbnail {meta.file_name}: {e}")

    def _select_active(self, photo: PhotoMeta) -> None:
        """Menandai foto sebagai aktif dan mengirim callback pratinjau."""
        self.active_photo = photo
        for path, card in self.card_widgets.items():
            card.set_active(path == photo.file_path)

        if self.on_select_photo:
            self.on_select_photo(photo)

    def _on_item_checked(self, photo: PhotoMeta, is_checked: bool) -> None:
        if is_checked:
            self.selected_set.add(photo.file_path)
        else:
            self.selected_set.discard(photo.file_path)

    def _select_all(self) -> None:
        for card in self.card_widgets.values():
            card.check_var.set(True)
            self.selected_set.add(card.meta.file_path)

    def _unselect_all(self) -> None:
        for card in self.card_widgets.values():
            card.check_var.set(False)
        self.selected_set.clear()

    def _delete_selected(self) -> None:
        if not self.selected_set:
            return
        to_del = set(self.selected_set)
        for p in to_del:
            card = self.card_widgets.pop(p, None)
            if card:
                card.destroy()

        self.photos = [p for p in self.photos if p.file_path not in to_del]
        self.selected_set.clear()

        if self.active_photo and self.active_photo.file_path in to_del:
            self.active_photo = self.photos[0] if self.photos else None
            if self.active_photo and self.on_select_photo:
                self.on_select_photo(self.active_photo)

        self._refresh_list_view()

    def _apply_location_to_selected(self) -> None:
        """Menyalin koordinat & alamat dari foto aktif ke semua foto yang dicentang."""
        if not self.active_photo:
            messagebox.showinfo("Informasi", "Pilih foto sumber lokasi terlebih dahulu.")
            return

        if not self.selected_set:
            messagebox.showinfo("Informasi", "Centang minimal satu foto target.")
            return

        count = 0
        for p in self.photos:
            if p.file_path in self.selected_set and p.file_path != self.active_photo.file_path:
                p.lat = self.active_photo.lat
                p.lon = self.active_photo.lon
                p.coords_source = "manual"
                p.street = self.active_photo.street
                p.district = self.active_photo.district
                p.regency = self.active_photo.regency
                p.province = self.active_photo.province
                p.address_source = self.active_photo.address_source
                p.altitude = self.active_photo.altitude
                p.heading = self.active_photo.heading
                p.is_modified_manually = True
                p.update_status()

                card = self.card_widgets.get(p.file_path)
                if card:
                    card.update_data()
                count += 1

        messagebox.showinfo("Berhasil", f"Data lokasi berhasil diterapkan ke {count} foto terpilih.")

    def _do_batch_geocoding(self) -> None:
        """Menjalankan reverse geocoding otomatis di background thread untuk foto ber-GPS."""
        need_geocode = [p for p in self.photos if p.lat is not None and p.lon is not None and not p.street]
        if not need_geocode:
            messagebox.showinfo("Informasi", "Semua foto ber-GPS sudah memiliki data alamat.")
            return

        self.btn_geocode_all.configure(text="Mengambil Alamat...", state="disabled")

        def worker():
            for item in need_geocode:
                res = self.geocoder.reverse_geocode(item.lat, item.lon, use_online=True)
                item.street = res.get("street", "Jalan Tanpa Nama")
                item.district = res.get("district", "-")
                item.regency = res.get("regency", "-")
                item.province = res.get("province", "-")
                item.address_source = res.get("source", "geocoding")
                item.update_status()

                card = self.card_widgets.get(item.file_path)
                if card:
                    self.after(0, card.update_data)

            self.after(0, lambda: self.btn_geocode_all.configure(text="🌐 Ambil Alamat Otomatis", state="normal"))
            self.after(0, lambda: messagebox.showinfo("Selesai", f"Geocoding selesai untuk {len(need_geocode)} foto."))

        threading.Thread(target=worker, daemon=True).start()

    def update_photo_item(self, photo: PhotoMeta) -> None:
        """Memperbarui kartu setelah edit modal selesai."""
        card = self.card_widgets.get(photo.file_path)
        if card:
            card.update_data()
