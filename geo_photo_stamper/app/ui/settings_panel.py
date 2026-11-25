"""
Panel pengaturan gaya overlay dan manajemen preset (SettingsPanel).
Mendukung kustomisasi lengkap posisi elemen, switch field teks, ukuran peta & kompas,
tipografi, warna, preset SQLite, serta impor/ekspor preset JSON.
Dilengkapi Quick Toggle di bagian atas untuk Border / Kotak Latar Belakang dan Tabview terorganisir.
"""

from __future__ import annotations
import json
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import customtkinter as ctk
from typing import Callable, Any
from pathlib import Path

from app.core.presets import OverlayStyle, get_default_style
from app.db.database import Database
from app.utils.fonts import get_available_system_fonts
from app.utils.logger import get_logger

logger = get_logger("SettingsPanel")

POSITION_MAP = {
    "Kanan Bawah": "bottom_right",
    "Kiri Bawah": "bottom_left",
    "Kanan Atas": "top_right",
    "Kiri Atas": "top_left",
    "Sembunyikan": "hidden"
}
REV_POSITION_MAP = {v: k for k, v in POSITION_MAP.items()}


class SettingsPanel(ctk.CTkFrame):
    """Panel pengaturan tampilan overlay dan manajemen template preset."""

    def __init__(
        self,
        parent: Any,
        db: Database,
        on_style_changed: Callable[[OverlayStyle], None]
    ) -> None:
        super().__init__(parent, corner_radius=10)
        self.db = db
        self.on_style_changed = on_style_changed
        self.style = get_default_style()
        self._updating_ui = False

        self._build_ui()
        self._load_saved_presets()

    def _build_ui(self) -> None:
        """Membangun layout antarmuka dengan Quick Toggle & Tabview terorganisir."""
        pad = 10

        # Header Panel
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=pad, pady=(pad, 4))

        ctk.CTkLabel(
            header,
            text="Pengaturan & Gaya",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left")

        # ---------------------------------------------------------------------
        # QUICK TOGGLE BANNER (Langsung terlihat di paling atas tanpa scrolling!)
        # ---------------------------------------------------------------------
        border_banner = ctk.CTkFrame(self, fg_color="#1E293B", corner_radius=8)
        border_banner.pack(fill="x", padx=pad, pady=(4, 6))

        banner_inner = ctk.CTkFrame(border_banner, fg_color="transparent")
        banner_inner.pack(fill="x", padx=10, pady=8)

        self.sw_bg_box = ctk.CTkSwitch(
            banner_inner,
            text="Border / Kotak Latar Belakang",
            font=ctk.CTkFont(size=12, weight="bold"),
            progress_color="#3B82F6",
            command=self._on_control_changed
        )
        self.sw_bg_box.select()  # Default Aktif
        self.sw_bg_box.pack(side="left")

        self.lbl_border_status = ctk.CTkLabel(
            banner_inner,
            text="(ON)",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#60A5FA"
        )
        self.lbl_border_status.pack(side="left", padx=6)

        # ---------------------------------------------------------------------
        # TABVIEW UNTUK MENGELOMPOKKAN PENGATURAN
        # ---------------------------------------------------------------------
        self.tabview = ctk.CTkTabview(self, corner_radius=8)
        self.tabview.pack(fill="both", expand=True, padx=pad, pady=(0, pad))

        tab_gaya = self.tabview.add("Gaya Teks")
        tab_peta = self.tabview.add("Peta & Kompas")
        tab_field = self.tabview.add("Field Data")
        tab_preset = self.tabview.add("Preset & Ekspor")

        # =====================================================================
        # TAB 1: GAYA & TIPOGRAFI
        # =====================================================================
        scroll_gaya = ctk.CTkScrollableFrame(tab_gaya, fg_color="transparent")
        scroll_gaya.pack(fill="both", expand=True, padx=2, pady=2)

        # Posisi Teks
        r_text_pos = ctk.CTkFrame(scroll_gaya, fg_color="transparent")
        r_text_pos.pack(fill="x", pady=4)
        ctk.CTkLabel(r_text_pos, text="Posisi Blok Teks:", width=120, anchor="w").pack(side="left")
        self.opt_text_pos = ctk.CTkOptionMenu(
            r_text_pos,
            values=["Kanan Bawah", "Kiri Bawah", "Kanan Atas", "Kiri Atas"],
            command=self._on_control_changed
        )
        self.opt_text_pos.pack(side="right", fill="x", expand=True)

        # Warna Teks
        r_col = ctk.CTkFrame(scroll_gaya, fg_color="transparent")
        r_col.pack(fill="x", pady=4)
        ctk.CTkLabel(r_col, text="Warna Teks:", width=120, anchor="w").pack(side="left")
        self.opt_color = ctk.CTkOptionMenu(
            r_col,
            values=["Putih", "Kuning Emas", "Hijau Terang", "Cyan Cerah"],
            command=self._on_control_changed
        )
        self.opt_color.pack(side="right", fill="x", expand=True)

        # Font Family
        r_font = ctk.CTkFrame(scroll_gaya, fg_color="transparent")
        r_font.pack(fill="x", pady=4)
        ctk.CTkLabel(r_font, text="Font:", width=120, anchor="w").pack(side="left")
        sys_fonts = get_available_system_fonts()
        self.opt_font = ctk.CTkOptionMenu(r_font, values=sys_fonts, command=self._on_control_changed)
        self.opt_font.pack(side="right", fill="x", expand=True)

        # Skala Font
        r_fscale = ctk.CTkFrame(scroll_gaya, fg_color="transparent")
        r_fscale.pack(fill="x", pady=4)
        ctk.CTkLabel(r_fscale, text="Ukuran Font:", width=120, anchor="w").pack(side="left")
        self.slider_fscale = ctk.CTkSlider(r_fscale, from_=0.7, to=1.6, number_of_steps=9, command=self._on_control_changed)
        self.slider_fscale.set(1.0)
        self.slider_fscale.pack(side="right", fill="x", expand=True)

        # Bayangan / Outline Teks
        r_shadow = ctk.CTkFrame(scroll_gaya, fg_color="transparent")
        r_shadow.pack(fill="x", pady=6)
        self.sw_outline = ctk.CTkSwitch(
            r_shadow,
            text="Bayangan Teks (Outline)",
            command=self._on_control_changed
        )
        self.sw_outline.select()
        self.sw_outline.pack(side="left")

        # Kepekatan Latar (Opacity)
        r_opac = ctk.CTkFrame(scroll_gaya, fg_color="transparent")
        r_opac.pack(fill="x", pady=(4, 6))
        ctk.CTkLabel(r_opac, text="Kepekatan Latar:", width=120, anchor="w").pack(side="left")
        self.slider_opacity = ctk.CTkSlider(r_opac, from_=40, to=240, command=self._on_control_changed)
        self.slider_opacity.set(140)
        self.slider_opacity.pack(side="right", fill="x", expand=True)

        # =====================================================================
        # TAB 2: PETA & KOMPAS
        # =====================================================================
        scroll_peta = ctk.CTkScrollableFrame(tab_peta, fg_color="transparent")
        scroll_peta.pack(fill="both", expand=True, padx=2, pady=2)

        # Peta Mini Switch & Posisi
        r_map_sw = ctk.CTkFrame(scroll_peta, fg_color="transparent")
        r_map_sw.pack(fill="x", pady=4)
        self.sw_map = ctk.CTkSwitch(r_map_sw, text="Tampilkan Peta Mini", command=self._on_control_changed)
        self.sw_map.select()
        self.sw_map.pack(side="left")

        r_map_pos = ctk.CTkFrame(scroll_peta, fg_color="transparent")
        r_map_pos.pack(fill="x", pady=4)
        ctk.CTkLabel(r_map_pos, text="Posisi Peta:", width=120, anchor="w").pack(side="left")
        self.opt_map_pos = ctk.CTkOptionMenu(
            r_map_pos,
            values=["Kiri Bawah", "Kanan Bawah", "Kiri Atas", "Kanan Atas"],
            command=self._on_control_changed
        )
        self.opt_map_pos.pack(side="right", fill="x", expand=True)

        # Slider Zoom Peta
        r_zoom = ctk.CTkFrame(scroll_peta, fg_color="transparent")
        r_zoom.pack(fill="x", pady=4)
        ctk.CTkLabel(r_zoom, text="Zoom Peta (10-18):", width=120, anchor="w").pack(side="left")
        self.slider_zoom = ctk.CTkSlider(r_zoom, from_=10, to=18, number_of_steps=8, command=self._on_control_changed)
        self.slider_zoom.set(15)
        self.slider_zoom.pack(side="right", fill="x", expand=True)

        # Kompas Switch & Posisi
        r_comp_sw = ctk.CTkFrame(scroll_peta, fg_color="transparent")
        r_comp_sw.pack(fill="x", pady=(10, 4))
        self.sw_compass = ctk.CTkSwitch(r_comp_sw, text="Tampilkan Kompas", command=self._on_control_changed)
        self.sw_compass.select()
        self.sw_compass.pack(side="left")

        r_comp_pos = ctk.CTkFrame(scroll_peta, fg_color="transparent")
        r_comp_pos.pack(fill="x", pady=4)
        ctk.CTkLabel(r_comp_pos, text="Posisi Kompas:", width=120, anchor="w").pack(side="left")
        self.opt_comp_pos = ctk.CTkOptionMenu(
            r_comp_pos,
            values=["Kiri Atas", "Kanan Atas", "Kiri Bawah", "Kanan Bawah"],
            command=self._on_control_changed
        )
        self.opt_comp_pos.pack(side="right", fill="x", expand=True)

        # =====================================================================
        # TAB 3: FIELD DATA YANG DICETAK
        # =====================================================================
        scroll_field = ctk.CTkScrollableFrame(tab_field, fg_color="transparent")
        scroll_field.pack(fill="both", expand=True, padx=2, pady=2)

        self.field_switches: dict[str, ctk.CTkSwitch] = {}
        fields = [
            ("show_date_time", "Tanggal dan Waktu"),
            ("show_heading", "Arah Kompas (° Heading)"),
            ("show_street", "Nama Jalan"),
            ("show_district", "Kecamatan / Kelurahan"),
            ("show_regency_province", "Kabupaten dan Provinsi"),
            ("show_altitude", "Ketinggian (Altitude)"),
            ("show_speed", "Kecepatan"),
            ("show_coords", "Koordinat GPS"),
            ("show_index", "Nomor Indeks Foto"),
            ("show_notes", "Catatan Tambahan")
        ]
        for attr, label_text in fields:
            sw = ctk.CTkSwitch(scroll_field, text=label_text, command=self._on_control_changed)
            sw.select()
            sw.pack(anchor="w", padx=6, pady=3)
            self.field_switches[attr] = sw

        # =====================================================================
        # TAB 4: PRESET & EKSPOR
        # =====================================================================
        scroll_pre = ctk.CTkScrollableFrame(tab_preset, fg_color="transparent")
        scroll_pre.pack(fill="both", expand=True, padx=2, pady=2)

        ctk.CTkLabel(scroll_pre, text="Pilihan Preset / Template:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0, 4))
        self.preset_menu = ctk.CTkOptionMenu(
            scroll_pre,
            values=["Default (GPS Camera)", "Tanpa Border (Clean)", "Minimalis (Waktu & GPS)", "Lengkap Lapangan"],
            command=self._on_select_preset
        )
        self.preset_menu.pack(fill="x", pady=(0, 8))

        row_pre_btn = ctk.CTkFrame(scroll_pre, fg_color="transparent")
        row_pre_btn.pack(fill="x", pady=(0, 10))

        btn_save_pre = ctk.CTkButton(row_pre_btn, text="Simpan Preset", width=100, fg_color="#3B82F6", command=self._save_custom_preset)
        btn_save_pre.pack(side="left", padx=(0, 6))

        btn_del_pre = ctk.CTkButton(row_pre_btn, text="Hapus", width=65, fg_color="#7F1D1D", command=self._delete_current_preset)
        btn_del_pre.pack(side="right")

        row_json_btn = ctk.CTkFrame(scroll_pre, fg_color="transparent")
        row_json_btn.pack(fill="x", pady=(0, 12))

        btn_exp = ctk.CTkButton(row_json_btn, text="Ekspor JSON", font=ctk.CTkFont(size=11), width=90, fg_color="gray30", command=self._export_preset_json)
        btn_exp.pack(side="left", padx=(0, 6))

        btn_imp = ctk.CTkButton(row_json_btn, text="Impor JSON", font=ctk.CTkFont(size=11), width=90, fg_color="gray30", command=self._import_preset_json)
        btn_imp.pack(side="left")

        # Nomor Indeks & Kualitas JPEG
        ctk.CTkLabel(scroll_pre, text="Pengaturan Batch & Output:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(8, 4))

        r_idx = ctk.CTkFrame(scroll_pre, fg_color="transparent")
        r_idx.pack(fill="x", pady=4)
        ctk.CTkLabel(r_idx, text="No. Indeks Awal:", width=120, anchor="w").pack(side="left")
        self.entry_index_start = ctk.CTkEntry(r_idx, width=70)
        self.entry_index_start.insert(0, "1")
        self.entry_index_start.pack(side="right")

        r_qual = ctk.CTkFrame(scroll_pre, fg_color="transparent")
        r_qual.pack(fill="x", pady=4)
        ctk.CTkLabel(r_qual, text="Kualitas JPEG (92):", width=120, anchor="w").pack(side="left")
        self.slider_qual = ctk.CTkSlider(r_qual, from_=75, to=100, number_of_steps=25)
        self.slider_qual.set(92)
        self.slider_qual.pack(side="right", fill="x", expand=True)

    def _on_control_changed(self, *args: Any) -> None:
        """Dipanggil setiap kali elemen pengaturan diubah oleh pengguna."""
        if self._updating_ui:
            return

        is_box_on = bool(self.sw_bg_box.get())
        self.style.show_bg_box = is_box_on
        self.lbl_border_status.configure(
            text="(ON)" if is_box_on else "(OFF)",
            text_color="#60A5FA" if is_box_on else "#94A3B8"
        )

        self.style.text_position = POSITION_MAP.get(self.opt_text_pos.get(), "bottom_right")
        self.style.show_map = bool(self.sw_map.get())
        self.style.map_position = POSITION_MAP.get(self.opt_map_pos.get(), "bottom_left")
        self.style.map_zoom = int(self.slider_zoom.get())

        self.style.show_compass = bool(self.sw_compass.get())
        self.style.compass_position = POSITION_MAP.get(self.opt_comp_pos.get(), "top_left")

        # Switches field
        for attr, sw in self.field_switches.items():
            setattr(self.style, attr, bool(sw.get()))

        # Tipografi & Latar
        self.style.font_name = self.opt_font.get()
        self.style.font_scale = round(float(self.slider_fscale.get()), 2)

        col_name = self.opt_color.get()
        if col_name == "Kuning Emas":
            self.style.text_color = "#FBBF24"
        elif col_name == "Hijau Terang":
            self.style.text_color = "#34D399"
        elif col_name == "Cyan Cerah":
            self.style.text_color = "#38BDF8"
        else:
            self.style.text_color = "#FFFFFF"

        self.style.bg_box_opacity = int(self.slider_opacity.get())
        self.style.text_outline = bool(self.sw_outline.get())

        try:
            self.style.index_start = int(self.entry_index_start.get().strip() or "1")
        except ValueError:
            self.style.index_start = 1

        if self.on_style_changed:
            self.on_style_changed(self.style)

    def _load_saved_presets(self) -> None:
        """Memuat daftar preset kustom dari database SQLite."""
        items = self.db.get_all_presets()
        default_names = ["Default (GPS Camera)", "Tanpa Border (Clean)", "Minimalis (Waktu & GPS)", "Lengkap Lapangan"]
        custom_names = [p["name"] for p in items]
        all_presets = default_names + custom_names
        self.preset_menu.configure(values=all_presets)

    def _on_select_preset(self, preset_name: str) -> None:
        """Memuat konfigurasi preset yang dipilih."""
        if preset_name == "Default (GPS Camera)":
            self.style = get_default_style()
            self.style.show_bg_box = True
        elif preset_name == "Tanpa Border (Clean)":
            self.style = get_default_style()
            self.style.show_bg_box = False
        elif preset_name == "Minimalis (Waktu & GPS)":
            self.style = get_default_style()
            self.style.show_bg_box = False
            self.style.show_compass = False
            self.style.show_map = False
            self.style.show_altitude = False
            self.style.show_speed = False
            self.style.show_district = False
            self.style.show_regency_province = False
        elif preset_name == "Lengkap Lapangan":
            self.style = get_default_style()
            self.style.show_bg_box = True
            self.style.show_coords = True
            self.style.show_notes = True
            self.style.show_compass = True
            self.style.show_map = True
        else:
            row = self.db.get_preset_by_name(preset_name)
            if row:
                try:
                    self.style = OverlayStyle.from_json(row["config_json"])
                except Exception as e:
                    logger.error(f"Gagal parse preset JSON {preset_name}: {e}")

        self._sync_ui_from_style()
        if self.on_style_changed:
            self.on_style_changed(self.style)

    def _sync_ui_from_style(self) -> None:
        """Menyesuaikan posisi switch & slider di antarmuka sesuai isi self.style."""
        self._updating_ui = True
        try:
            if self.style.show_bg_box:
                self.sw_bg_box.select()
                self.lbl_border_status.configure(text="(ON)", text_color="#60A5FA")
            else:
                self.sw_bg_box.deselect()
                self.lbl_border_status.configure(text="(OFF)", text_color="#94A3B8")

            self.opt_text_pos.set(REV_POSITION_MAP.get(self.style.text_position, "Kanan Bawah"))
            if self.style.show_map:
                self.sw_map.select()
            else:
                self.sw_map.deselect()

            self.opt_map_pos.set(REV_POSITION_MAP.get(self.style.map_position, "Kiri Bawah"))
            self.slider_zoom.set(self.style.map_zoom)

            if self.style.show_compass:
                self.sw_compass.select()
            else:
                self.sw_compass.deselect()

            self.opt_comp_pos.set(REV_POSITION_MAP.get(self.style.compass_position, "Kiri Atas"))

            for attr, sw in self.field_switches.items():
                if getattr(self.style, attr, True):
                    sw.select()
                else:
                    sw.deselect()

            self.slider_fscale.set(self.style.font_scale)
            self.slider_opacity.set(self.style.bg_box_opacity)
            if self.style.text_outline:
                self.sw_outline.select()
            else:
                self.sw_outline.deselect()
        finally:
            self._updating_ui = False

    def _save_custom_preset(self) -> None:
        """Menyimpan preset baru ke SQLite."""
        name = simpledialog.askstring("Simpan Preset", "Masukkan nama template preset:")
        if name and name.strip():
            self._on_control_changed()
            self.db.save_preset(name.strip(), self.style.to_json())
            self._load_saved_presets()
            self.preset_menu.set(name.strip())
            messagebox.showinfo("Berhasil", f"Preset '{name.strip()}' berhasil disimpan.")

    def _delete_current_preset(self) -> None:
        """Menghapus preset kustom."""
        cur = self.preset_menu.get()
        if cur in ["Default (GPS Camera)", "Tanpa Border (Clean)", "Minimalis (Waktu & GPS)", "Lengkap Lapangan"]:
            messagebox.showwarning("Peringatan", "Preset bawaan sistem tidak dapat dihapus.")
            return

        if messagebox.askyesno("Konfirmasi", f"Hapus preset '{cur}'?"):
            self.db.delete_preset(cur)
            self._load_saved_presets()
            self.preset_menu.set("Default (GPS Camera)")
            self._on_select_preset("Default (GPS Camera)")

    def _export_preset_json(self) -> None:
        """Mengekspor preset aktif ke file JSON."""
        file_path = filedialog.asksaveasfilename(
            title="Ekspor Preset Gaya",
            defaultextension=".json",
            filetypes=[("File JSON", "*.json")]
        )
        if file_path:
            self._on_control_changed()
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.style.to_json())
            messagebox.showinfo("Berhasil", f"Preset berhasil diekspor ke: {file_path}")

    def _import_preset_json(self) -> None:
        """Mengimpor konfigurasi preset dari file JSON."""
        file_path = filedialog.askopenfilename(
            title="Impor Preset Gaya",
            filetypes=[("File JSON", "*.json")]
        )
        if file_path and Path(file_path).exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.style = OverlayStyle.from_json(content)
                self._sync_ui_from_style()
                if self.on_style_changed:
                    self.on_style_changed(self.style)
                messagebox.showinfo("Berhasil", "Preset berhasil diimpor.")
            except Exception as e:
                messagebox.showerror("Gagal", f"Gagal membaca file JSON: {e}")
