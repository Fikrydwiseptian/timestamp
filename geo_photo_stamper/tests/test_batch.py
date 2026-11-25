"""
Unit tests untuk validasi modul Geo Photo Stamper:
1. Uji konversi GPS DMS ke desimal.
2. Uji penomoran indeks otomatis.
3. Uji penamaan unik file output.
4. Uji integritas file asli tidak berubah (hash SHA-256).
"""

import unittest
import tempfile
import os
import shutil
from pathlib import Path
from PIL import Image

from app.core.exif_reader import _convert_dms_to_decimal, PhotoMeta
from app.core.batch import get_unique_output_path, get_file_sha256, BatchProcessor
from app.core.presets import get_default_style
from app.db.database import Database


class TestGeoPhotoStamper(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = Database(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_gps_dms_to_decimal(self):
        """Uji konversi koordinat DMS ke desimal."""
        # 7°15'30" S -> -7.258333...
        dms = ((7, 1), (15, 1), (30, 1))
        dec = _convert_dms_to_decimal(dms, "S")
        self.assertAlmostEqual(dec, -7.2583333, places=5)

        # 110°20'00" E -> +110.333333...
        dms_e = ((110, 1), (20, 1), (0, 1))
        dec_e = _convert_dms_to_decimal(dms_e, "E")
        self.assertAlmostEqual(dec_e, 110.333333, places=5)

    def test_unique_output_path(self):
        """Uji pencegahan penimpaan file output dengan suffix angka bertingkat."""
        out_dir = Path(self.temp_dir)
        filename = "inspeksi.jpg"

        p1 = get_unique_output_path(out_dir, filename, "_stamped")
        self.assertEqual(p1.name, "inspeksi_stamped.jpg")

        # Buat file fisik p1
        p1.touch()

        p2 = get_unique_output_path(out_dir, filename, "_stamped")
        self.assertEqual(p2.name, "inspeksi_stamped_1.jpg")

        p2.touch()
        p3 = get_unique_output_path(out_dir, filename, "_stamped")
        self.assertEqual(p3.name, "inspeksi_stamped_2.jpg")

    def test_original_file_hash_unmodified(self):
        """Uji ketat bahwa pemrosesan batch TIDAK PERNAH mengubah hash file asli."""
        test_img_path = Path(self.temp_dir) / "test_photo.jpg"
        img = Image.new("RGB", (400, 300), color=(100, 150, 200))
        img.save(test_img_path, format="JPEG")

        initial_sha = get_file_sha256(test_img_path)

        meta = PhotoMeta(
            file_path=str(test_img_path),
            file_name="test_photo.jpg",
            date_time="2026-10-29 10:00:00",
            lat=-6.1754,
            lon=106.8272,
            street="Jl. Medan Merdeka",
            district="Kecamatan Gambir",
            regency="Kota Jakarta Pusat",
            province="DKI Jakarta"
        )

        out_dir = Path(self.temp_dir) / "output"
        processor = BatchProcessor(db=self.db, max_workers=1)
        res = processor.process_photos(
            photos=[meta],
            style=get_default_style(),
            output_dir=out_dir
        )

        final_sha = get_file_sha256(test_img_path)
        self.assertEqual(initial_sha, final_sha, "Hash foto asli berubah!")
        self.assertEqual(res["success"], 1)
        self.assertEqual(res["failed"], 0)


if __name__ == "__main__":
    unittest.main()
