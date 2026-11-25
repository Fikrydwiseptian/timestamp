"""
Panel pratinjau tengah (PreviewPanel).
Menampilkan pratinjau foto terpilih dengan overlay stempel secara langsung (live preview),
mendukung debouncing 300ms saat pengaturan diubah, pemilihan folder output,
dan tombol kontrol eksekusi batch ("PROSES SEMUA" dan "Batal").
"""

from __future__ import annotations
import os
import threading
from pathlib import Path
from typing import Callable, Any
from tkinter import filedialog
import customtkinter as ctk
from PIL import Image

from app.core.exif_reader import PhotoMeta, load_and_orient_image
from app.core.presets import OverlayStyle
from app.core.overlay import render_overlay
from app.utils.paths import get_default_output_dir
from app.utils.logger import get_logger

logger = get_logger("PreviewPanel")


class PreviewPanel(ctk.CTkFrame):
    """Panel pratinjau foto dengan overlay real-time dan kontrol eksekusi batch."""

    def __init__(
        self,
        parent: Any,
        on_start_batch: Callable[[Path, str], None],
        on_cancel_batch: Callable[[], None]
    ) -> None:
        super().__init__(parent, corner_radius=10)
        self.on_start_batch = on_start_batch
        self.on_cancel_batch = on_cancel_batch

        self.current_photo: PhotoMeta | None = None
        self.current_style: OverlayStyle | None = None

        self._debounce_timer: threading.Timer | None = None
        self._rendered_preview_cache: ctk.CTkImage | None = None
        self._base_preview_img: Image.Image | None = None
        self._cached_photo_path: str = ""

        self._build_ui()

    def _build_ui(self) -> None:
        """Membangun tata letak UI panel pratinjau."""
        # Top Title & Meta Info Bar
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=15, pady=(12, 6))

        self.lbl_title = ctk.CTkLabel(
            top_bar,
            text="Pratinjau Stempel",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.lbl_title.pack(side="left")

        self.lbl_info = ctk.CTkLabel(
            top_bar,
            text="Pilih foto di panel kiri untuk melihat pratinjau",
            font=ctk.CTkFont(size=12),
            text_color="gray70"
        )
        self.lbl_info.pack(side="right")

        # Canvas Frame untuk Gambar Pratinjau
        self.preview_canvas_frame = ctk.CTkFrame(self, fg_color="gray12", corner_radius=8)
        self.preview_canvas_frame.pack(fill="both", expand=True, padx=12, pady=6)

        self.lbl_image = ctk.CTkLabel(
            self.preview_canvas_frame,
            text="[ Area Pratinjau Foto ]",
            text_color="gray50",
            font=ctk.CTkFont(size=14)
        )
        self.lbl_image.pack(expand=True, fill="both", padx=10, pady=10)

        # -----------------------------------------------------------------
        # Panel Kontrol Output & Eksekusi Batch
        # -----------------------------------------------------------------
        bottom_frame = ctk.CTkFrame(self, fg_color="gray15", corner_radius=8)
        bottom_frame.pack(fill="x", padx=12, pady=(6, 12))

        # Baris 1: Folder Tujuan Output & Suffix
        row_out = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        row_out.pack(fill="x", padx=12, pady=(10, 6))

        ctk.CTkLabel(row_out, text="Folder Output:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 6))
        self.entry_output = ctk.CTkEntry(row_out, placeholder_text="Pilih folder tujuan output...")
        self.entry_output.pack(side="left", fill="x", expand=True, padx=(0, 6))

        btn_browse_out = ctk.CTkButton(
            row_out,
            text="Pilih Folder",
            width=90,
            command=self._on_browse_output
        )
        btn_browse_out.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(row_out, text="Akhiran:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 4))
        self.entry_suffix = ctk.CTkEntry(row_out, width=90)
        self.entry_suffix.insert(0, "_stamped")
        self.entry_suffix.pack(side="left")

        # Baris 2: Progress Bar & Tombol Proses
        row_act = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        row_act.pack(fill="x", padx=12, pady=(4, 10))

        # Frame Progress
        self.prog_frame = ctk.CTkFrame(row_act, fg_color="transparent")
        self.prog_frame.pack(side="left", fill="x", expand=True, padx=(0, 12))

        self.lbl_progress_status = ctk.CTkLabel(
            self.prog_frame,
            text="Siap untuk memproses",
            font=ctk.CTkFont(size=11),
            text_color="gray70",
            anchor="w"
        )
        self.lbl_progress_status.pack(fill="x")

        self.progress_bar = ctk.CTkProgressBar(self.prog_frame, height=10)
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", pady=(2, 0))

        # Tombol Batal (Sembunyi secara default)
        self.btn_cancel = ctk.CTkButton(
            row_act,
            text="Batal",
            width=80,
            fg_color="#DC2626",
            hover_color="#B91C1C",
            command=self.on_cancel_batch
        )
        self.btn_cancel.pack(side="right", padx=(8, 0))
        self.btn_cancel.pack_forget()

        # Tombol Utama: PROSES SEMUA
        self.btn_process = ctk.CTkButton(
            row_act,
            text="⚡ PROSES SEMUA",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#10B981",
            hover_color="#059669",
            height=34,
            width=150,
            command=self._on_start_click
        )
        self.btn_process.pack(side="right")

    def _on_browse_output(self) -> None:
        """Dialog pemilihan folder tujuan ekspor."""
        selected = filedialog.askdirectory(title="Pilih Folder Output Hasil Stempel")
        if selected:
            self.entry_output.delete(0, "end")
            self.entry_output.insert(0, selected)

    def _on_start_click(self) -> None:
        """Menjalankan proses batch."""
        out_dir_str = self.entry_output.get().strip()
        if not out_dir_str:
            if self.current_photo:
                out_dir_str = str(get_default_output_dir(self.current_photo.file_path))
            else:
                out_dir_str = str(get_default_output_dir(None))
            self.entry_output.insert(0, out_dir_str)

        suffix = self.entry_suffix.get().strip() or "_stamped"
        self.on_start_batch(Path(out_dir_str), suffix)

    def set_batch_running(self, running: bool) -> None:
        """Mengatur status tombol saat batch berjalan."""
        if running:
            self.btn_process.configure(state="disabled")
            self.btn_cancel.pack(side="right", padx=(8, 0))
            self.progress_bar.set(0.0)
        else:
            self.btn_process.configure(state="normal")
            self.btn_cancel.pack_forget()

    def update_progress(self, current: int, total: int, current_file: str, status: str) -> None:
        """Memperbarui visualisasi progress bar dan teks status."""
        pct = current / total if total > 0 else 0.0
        self.progress_bar.set(pct)
        self.lbl_progress_status.configure(
            text=f"Memproses {current}/{total} ({int(pct * 100)}%): {current_file} [{status}]"
        )

    def set_photo_and_style(self, photo: PhotoMeta | None, style: OverlayStyle) -> None:
        """Memperbarui foto dan konfigurasi gaya overlay yang ingin ditampilkan."""
        self.current_photo = photo
        self.current_style = style

        if not photo:
            self.lbl_image.configure(image="", text="[ Tidak Ada Foto yang Dipilih ]")
            self.lbl_info.configure(text="")
            return

        # Atur default output dir jika kosong
        if not self.entry_output.get().strip():
            default_out = get_default_output_dir(photo.file_path)
            self.entry_output.insert(0, str(default_out))

        self.lbl_title.configure(text=f"Pratinjau: {photo.file_name}")
        self.lbl_info.configure(text=f"Resolusi Asli: {photo.width} x {photo.height}")

        # Debounce re-render 300 ms agar slider gaya responsif tanpa lag
        if self._debounce_timer is not None:
            self._debounce_timer.cancel()

        self._debounce_timer = threading.Timer(0.3, self._render_preview_worker)
        self._debounce_timer.start()

    def _render_preview_worker(self) -> None:
        """Menghasilkan overlay pratinjau di thread background pada resolusi optimal."""
        if not self.current_photo or not self.current_style:
            return

        try:
            # 1. Buka foto dasar jika belum di-cache
            if self._cached_photo_path != self.current_photo.file_path or self._base_preview_img is None:
                full_img = load_and_orient_image(self.current_photo.file_path)
                # Perkecil ke resolusi max 1280px agar render cepat
                preview_scale_img = full_img.copy()
                preview_scale_img.thumbnail((1280, 800), Image.Resampling.BILINEAR)
                self._base_preview_img = preview_scale_img
                self._cached_photo_path = self.current_photo.file_path

            # 2. Render overlay pada base image
            stamped = render_overlay(self._base_preview_img, self.current_photo, self.current_style)

            # 3. Konversi ke CTkImage untuk ditampilkan di widget UI
            pw, ph = stamped.size
            # Hitung ukuran muat di area tampilan (misal ~640 x 420)
            target_w = 640
            target_h = int(ph * (target_w / pw)) if pw > 0 else 400
            if target_h > 460:
                target_h = 460
                target_w = int(pw * (target_h / ph)) if ph > 0 else 640

            ctk_img = ctk.CTkImage(light_image=stamped, dark_image=stamped, size=(target_w, target_h))

            # Update ke UI di thread utama
            self.after(0, lambda: self._apply_preview_image(ctk_img))

        except Exception as e:
            logger.error(f"Gagal me-render pratinjau: {e}")

    def _apply_preview_image(self, ctk_img: ctk.CTkImage) -> None:
        """Memasang CTkImage ke widget label pratinjau."""
        self._rendered_preview_cache = ctk_img
        self.lbl_image.configure(image=ctk_img, text="")
