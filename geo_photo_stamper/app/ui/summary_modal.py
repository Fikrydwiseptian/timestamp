"""
Modal dialog ringkasan hasil pemrosesan batch stempel foto.
"""

from __future__ import annotations
import os
import customtkinter as ctk
from typing import Any
from app.utils.logger import get_logger

logger = get_logger("SummaryModal")


class BatchSummaryModal(ctk.CTkToplevel):
    """Jendela modal ringkasan setelah batch pemrosesan selesai."""

    def __init__(self, parent: Any, summary: dict[str, Any]) -> None:
        super().__init__(parent)
        self.summary = summary

        self.title("Ringkasan Pemrosesan Batch")
        self.geometry("560x480")
        self.minsize(480, 400)
        self.transient(parent)
        self.grab_set()

        self._build_ui()

    def _build_ui(self) -> None:
        """Membangun tampilan ringkasan hasil."""
        pad = 20

        # Judul
        ctk.CTkLabel(
            self,
            text="Proses Batch Selesai",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(anchor="w", padx=pad, pady=(20, 10))

        # Status Cards Frame
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", padx=pad, pady=(0, 15))

        # Total Card
        c_total = ctk.CTkFrame(cards_frame, corner_radius=8)
        c_total.pack(side="left", fill="both", expand=True, padx=(0, 6))
        ctk.CTkLabel(c_total, text="Total Foto", font=ctk.CTkFont(size=12)).pack(pady=(10, 0))
        ctk.CTkLabel(c_total, text=str(self.summary.get("total", 0)), font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(0, 10))

        # Success Card
        c_succ = ctk.CTkFrame(cards_frame, fg_color="#064E3B", corner_radius=8)
        c_succ.pack(side="left", fill="both", expand=True, padx=6)
        ctk.CTkLabel(c_succ, text="Berhasil", font=ctk.CTkFont(size=12), text_color="#A7F3D0").pack(pady=(10, 0))
        ctk.CTkLabel(c_succ, text=str(self.summary.get("success", 0)), font=ctk.CTkFont(size=24, weight="bold"), text_color="#34D399").pack(pady=(0, 10))

        # Failed Card
        c_fail = ctk.CTkFrame(cards_frame, fg_color="#7F1D1D" if self.summary.get("failed", 0) > 0 else "gray20", corner_radius=8)
        c_fail.pack(side="left", fill="both", expand=True, padx=(6, 0))
        ctk.CTkLabel(c_fail, text="Gagal", font=ctk.CTkFont(size=12), text_color="#FECACA").pack(pady=(10, 0))
        ctk.CTkLabel(c_fail, text=str(self.summary.get("failed", 0)), font=ctk.CTkFont(size=24, weight="bold"), text_color="#F87171").pack(pady=(0, 10))

        # Daftar File Gagal (Jika ada)
        failed_items = [d for d in self.summary.get("details", []) if d.get("status") == "GAGAL"]
        if failed_items:
            ctk.CTkLabel(self, text="Daftar Foto yang Gagal:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=pad, pady=(0, 5))
            fail_scroll = ctk.CTkScrollableFrame(self, height=140)
            fail_scroll.pack(fill="both", expand=True, padx=pad, pady=(0, 15))
            for f in failed_items:
                row = ctk.CTkFrame(fail_scroll, fg_color="transparent")
                row.pack(fill="x", pady=2)
                ctk.CTkLabel(row, text=f.get("filename", ""), font=ctk.CTkFont(weight="bold"), text_color="#F87171").pack(side="left")
                ctk.CTkLabel(row, text=f"({f.get('error', '')})", text_color="gray70").pack(side="left", padx=8)
        else:
            msg_box = ctk.CTkFrame(self, fg_color="transparent")
            msg_box.pack(fill="both", expand=True, padx=pad, pady=(10, 15))
            ctk.CTkLabel(
                msg_box,
                text="🎉 Seluruh foto berhasil distempel tanpa kendala!",
                font=ctk.CTkFont(size=14),
                text_color="#10B981"
            ).pack(expand=True)

        # Tombol Aksi
        btn_bar = ctk.CTkFrame(self, fg_color="transparent")
        btn_bar.pack(fill="x", padx=pad, pady=(0, 20))

        btn_close = ctk.CTkButton(btn_bar, text="Tutup", width=100, command=self.destroy)
        btn_close.pack(side="right", padx=(8, 0))

        btn_open_folder = ctk.CTkButton(
            btn_bar,
            text="📁 Buka Folder Hasil",
            fg_color="#0284C7",
            hover_color="#0369A1",
            command=self._open_output_folder
        )
        btn_open_folder.pack(side="right")

    def _open_output_folder(self) -> None:
        """Membuka folder output di Windows Explorer."""
        out_dir = self.summary.get("output_dir", "")
        if out_dir and os.path.exists(out_dir):
            try:
                os.startfile(out_dir)
            except Exception as e:
                logger.error(f"Gagal membuka folder output: {e}")
