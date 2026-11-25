"""
Titik Masuk Utama (Main Entry Point) Aplikasi Geo Photo Stamper.
"""

from __future__ import annotations
import sys
from pathlib import Path

# Pastikan folder geo_photo_stamper ada dalam path pencarian modul Python
root_path = Path(__file__).resolve().parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from app.utils.logger import get_logger
from app.ui.main_window import MainWindow

logger = get_logger("Main")


def main() -> None:
    """Menjalankan siklus hidup aplikasi desktop."""
    logger.info("Memulai Geo Photo Stamper Desktop Application...")
    try:
        app = MainWindow()
        app.mainloop()
    except Exception as e:
        logger.critical(f"Kesalahan fatal saat menjalankan aplikasi: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
