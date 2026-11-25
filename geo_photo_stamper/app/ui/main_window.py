"""
Jendela utama aplikasi Geo Photo Stamper (MainWindow).
Menghubungkan panel daftar foto (kiri), pratinjau (tengah), dan pengaturan (kanan).
Mendukung mode gelap CustomTkinter, drag and drop file/folder, serta integrasi pemrosesan batch.
"""

from __future__ import annotations
import os
import threading
from pathlib import Path
from tkinter import messagebox
import customtkinter as ctk

# Integrasi opsional TkinterDnD2 untuk Drag and Drop
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except Exception:
    HAS_DND = False

from app.core.exif_reader import PhotoMeta
from app.core.presets import OverlayStyle
from app.core.geocoder import GeocoderService
from app.core.batch import BatchProcessor
from app.db.database import Database
from app.ui.photo_list import PhotoListPanel
from app.ui.preview_panel import PreviewPanel
from app.ui.settings_panel import SettingsPanel
from app.ui.edit_modal import EditPhotoModal
from app.ui.summary_modal import BatchSummaryModal
from app.utils.paths import get_app_data_dir
from app.utils.logger import get_logger

logger = get_logger("MainWindow")


class MainWindow(ctk.CTk):
    """Jendela utama aplikasi desktop Geo Photo Stamper."""

    def __init__(self) -> None:
        super().__init__()

        # Konfigurasi Tema
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Geo Photo Stamper - Sucofindo Field Documentation")
        self.geometry("1280x750")
        self.minsize(980, 600)

        # Inisialisasi Layanan Inti
        self.db = Database()
        self.geocoder = GeocoderService(db=self.db)
        self.batch_processor = BatchProcessor(db=self.db)

        self._active_photo: PhotoMeta | None = None
        self._current_style: OverlayStyle | None = None

        self._build_layout()
        self._setup_dnd()

    def _build_layout(self) -> None:
        """Menyusun tata letak 3 panel utama."""
        # Header Aplikasi
        header = ctk.CTkFrame(self, height=44, corner_radius=0, fg_color="#0F172A")
        header.pack(fill="x", side="top")

        ctk.CTkLabel(
            header,
            text="🏷️ Geo Photo Stamper",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#38BDF8"
        ).pack(side="left", padx=16)

        ctk.CTkLabel(
            header,
            text="Dokumentasi Foto Lapangan & Stempel GPS Otomatis",
            font=ctk.CTkFont(size=12),
            text_color="gray60"
        ).pack(side="left", padx=4)

        btn_about = ctk.CTkButton(
            header,
            text="Tentang",
            width=70,
            height=26,
            fg_color="gray25",
            hover_color="gray35",
            command=self._show_about
        )
        btn_about.pack(side="right", padx=12, pady=8)

        # Main Workspace Container
        workspace = ctk.CTkFrame(self, fg_color="transparent")
        workspace.pack(fill="both", expand=True, padx=10, pady=10)

        # 1. Panel Kiri: Daftar Foto (Lebar ~340px)
        self.panel_left = PhotoListPanel(
            workspace,
            geocoder=self.geocoder,
            on_select_photo=self._on_photo_selected,
            on_edit_photo=self._on_edit_photo_requested
        )
        self.panel_left.pack(side="left", fill="y", padx=(0, 6))
        self.panel_left.configure(width=340)

        # 2. Panel Kanan: Pengaturan & Gaya (Lebar ~340px)
        self.panel_right = SettingsPanel(
            workspace,
            db=self.db,
            on_style_changed=self._on_style_changed
        )
        self.panel_right.pack(side="right", fill="y", padx=(6, 0))
        self.panel_right.configure(width=340)

        # 3. Panel Tengah: Pratinjau & Eksekusi Batch (Expand)
        self.panel_center = PreviewPanel(
            workspace,
            on_start_batch=self._start_batch_processing,
            on_cancel_batch=self._cancel_batch_processing
        )
        self.panel_center.pack(side="left", fill="both", expand=True)

        # Sinkronisasi awal gaya
        self._current_style = self.panel_right.style

    def _setup_dnd(self) -> None:
        """Mengaktifkan fitur drag and drop file foto jika library didukung."""
        if not HAS_DND:
            logger.info("TkinterDnD tidak tersedia, drag and drop dimatikan.")
            return

        try:
            # Daftarkan drop target pada window utama
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_dnd_drop)
            logger.info("Drag and drop berhasil diaktifkan.")
        except Exception as e:
            logger.debug(f"Gagal menginisialisasi DnD: {e}")

    def _on_dnd_drop(self, event: Any) -> None:
        """Handler ketika pengguna menarik (drag) file atau folder ke jendela aplikasi."""
        raw_data = event.data
        if not raw_data:
            return

        # Parsing path file dari Tkinter DnD (bisa berupa daftar path berjarak spasi/kurung kurawal)
        paths = []
        if "{" in raw_data:
            # File dengan spasi terbungkus {...}
            import re
            matches = re.findall(r"\{(.*?)\}", raw_data)
            paths = matches
        else:
            paths = raw_data.split()

        clean_paths = [p.strip() for p in paths if os.path.exists(p.strip())]
        if clean_paths:
            self.panel_left.add_files_by_paths(clean_paths)

    def _on_photo_selected(self, photo: PhotoMeta) -> None:
        """Handler ketika foto pada daftar dipilih."""
        self._active_photo = photo
        if self._current_style:
            self.panel_center.set_photo_and_style(photo, self._current_style)

    def _on_style_changed(self, style: OverlayStyle) -> None:
        """Handler ketika pengguna mengubah gaya di panel kanan."""
        self._current_style = style
        if self._active_photo:
            self.panel_center.set_photo_and_style(self._active_photo, style)

    def _on_edit_photo_requested(self, photo: PhotoMeta) -> None:
        """Membuka jendela modal edit data manual foto."""
        def handle_saved(updated_photo: PhotoMeta):
            self.panel_left.update_photo_item(updated_photo)
            if self._current_style:
                self.panel_center.set_photo_and_style(updated_photo, self._current_style)

        EditPhotoModal(
            parent=self,
            photo=photo,
            geocoder=self.geocoder,
            on_save=handle_saved
        )

    def _start_batch_processing(self, output_dir: Path, suffix: str) -> None:
        """Menjalankan proses batch overlay foto dalam thread worker."""
        photos_to_process = self.panel_left.photos
        if not photos_to_process:
            messagebox.showwarning("Peringatan", "Belum ada foto dalam daftar untuk diproses.")
            return

        if not self._current_style:
            self._current_style = self.panel_right.style

        # Hitung nomor indeks berurutan jika diaktifkan
        start_idx = self._current_style.index_start
        for i, p in enumerate(photos_to_process):
            p.index_no = start_idx + i

        self.panel_center.set_batch_running(True)

        def progress_callback(cur: int, total: int, filename: str, status: str):
            self.after(0, lambda: self.panel_center.update_progress(cur, total, filename, status))

        def completion_callback(summary: dict[str, Any]):
            self.after(0, lambda: self._on_batch_finished(summary))

        def worker():
            quality = int(self.panel_right.slider_qual.get())
            self.batch_processor.process_photos(
                photos=photos_to_process,
                style=self._current_style,
                output_dir=output_dir,
                file_suffix=suffix,
                jpeg_quality=quality,
                on_progress=progress_callback,
                on_complete=completion_callback
            )

        threading.Thread(target=worker, daemon=True).start()

    def _cancel_batch_processing(self) -> None:
        """Membatalkan batch yang sedang berjalan."""
        self.batch_processor.cancel()

    def _on_batch_finished(self, summary: dict[str, Any]) -> None:
        """Dipanggil di thread utama saat proses batch selesai."""
        self.panel_center.set_batch_running(False)
        self.panel_center.lbl_progress_status.configure(
            text=f"Batch Selesai: {summary.get('success', 0)} Berhasil, {summary.get('failed', 0)} Gagal."
        )

        # Refresh status tiap kartu di panel kiri
        for photo in self.panel_left.photos:
            self.panel_left.update_photo_item(photo)

        # Tampilkan Modal Ringkasan Akhir
        BatchSummaryModal(self, summary)

    def _show_about(self) -> None:
        """Menampilkan dialog tentang aplikasi."""
        msg = (
            "Geo Photo Stamper v1.0\n"
            "Aplikasi Desktop Stempel Timestamp & GPS Map Camera\n\n"
            "Fitur:\n"
            "• Overlay Waktu, Alamat, Ketinggian, Arah & Kecepatan\n"
            "• Peta Mini OpenStreetMap & Kompas Vektor Otomatis\n"
            "• Reverse Geocoding dengan Nominatim & Cache SQLite\n"
            "• Ekspor Log CSV Audit Trail\n"
            "• Foto Asli Terjamin Tidak Berubah (Validasi Hash SHA-256)\n\n"
            f"Lokasi Data: {get_app_data_dir()}"
        )
        messagebox.showinfo("Tentang Geo Photo Stamper", msg)
