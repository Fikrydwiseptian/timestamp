# Geo Photo Stamper

Aplikasi desktop Windows mandiri berbasis **CustomTkinter** untuk menambahkan stempel timestamp dan informasi lokasi (gaya *GPS Map Camera*) ke banyak foto sekaligus secara batch.

Dikembangkan sesuai dokumen **PRD & Superprompt: Geo Photo Stamper**.

---

## 🌟 Fitur Utama

1. **Batch Overlay Otomatis**:
   - Membaca metadata EXIF asli kamera: tanggal & jam, koordinat GPS (DMS ke desimal), arah kompas (heading), ketinggian (altitude), dan kecepatan.
   - Peta mini OpenStreetMap dengan penanda pin merah di titik koordinat persis beserta atribusi lisensi OSM.
   - Kompas vektor berputar anti-aliased sesuai sudut heading pemotretan.
   - Blok teks informasi lengkap di kanan bawah dengan bayangan/outline dan latar transparan elegan.
2. **Reverse & Forward Geocoding (Nominatim / OpenStreetMap)**:
   - Rate limiting aman (> 1 detik per permintaan) dengan cache lokal SQLite (`%APPDATA%/GeoPhotoStamper/geophotostamper.db`).
   - Ekstraksi otomatis: Nama Jalan, Kecamatan, Kabupaten/Kota, dan Provinsi.
   - Mode offline: Menggunakan cache lokal atau isian manual saat tidak ada koneksi internet.
   - Fitur pencarian tempat untuk mengisi koordinat secara manual.
3. **Penyuntingan & Integritas Data**:
   - Form sunting data per foto atau terapkan lokasi massal ke foto yang dipilih.
   - Banner peringatan visual jika waktu atau GPS diubah berbeda dari EXIF asli.
   - Validasi hash SHA-256: **Foto asli dijamin tidak pernah diubah atau ditimpa**.
   - Ekspor log audit trail CSV lengkap dengan status dan sumber tiap nilai yang dicetak.
4. **Penskalaan Proporsional & Template**:
   - Skala ukuran otomatis terhadap resolusi foto (12 MP hingga 48 MP tetap proporsional).
   - Simpan, muat, ekspor, dan impor preset gaya tampilan (JSON).

---

## 📁 Struktur Direktori

```
geo_photo_stamper/
├── main.py                  # Entry point aplikasi desktop
├── requirements.txt         # Daftar pustaka dependensi
├── build.spec               # Spesifikasi PyInstaller untuk build .exe
├── app/
│   ├── ui/                  # Komponen antarmuka CustomTkinter
│   │   ├── main_window.py   # Jendela utama 3-panel
│   │   ├── photo_list.py    # Panel daftar foto & thumbnail
│   │   ├── preview_panel.py # Panel pratinjau live & progress batch
│   │   ├── settings_panel.py# Panel konfigurasi gaya & preset
│   │   ├── edit_modal.py    # Dialog sunting manual & pencarian tempat
│   │   └── summary_modal.py # Dialog ringkasan batch run
│   ├── core/                # Mesin inti pemrosesan foto
│   │   ├── exif_reader.py   # Pembaca EXIF & kalkulasi GPS
│   │   ├── geocoder.py      # Nominatim reverse/forward geocoding
│   │   ├── map_renderer.py  # Render tile OpenStreetMap & pin merah
│   │   ├── compass.py       # Gambar kompas vektor Pillow
│   │   ├── overlay.py       # Penggambar overlay stempel utama
│   │   ├── presets.py       # Model data OverlayStyle
│   │   └── batch.py         # Multi-threaded batch processor & CSV audit
│   ├── db/
│   │   └── database.py      # SQLite: cache geocode, preset, log
│   └── utils/
│       ├── paths.py         # Pengelola path %APPDATA% & aset
│       ├── logger.py        # Rotating file log
│       └── fonts.py         # Loader font sistem Windows
├── assets/                  # Ikon & aset statis
└── tests/
    ├── test_batch.py        # Unit test GPS, hash, & batch
    └── demo_overlay.py      # Skrip demo pembuatan sampel stempel
```

---

## 🚀 Cara Menjalankan

### 1. Instalasi Dependensi
```bash
pip install -r geo_photo_stamper/requirements.txt
```

### 2. Menjalankan Aplikasi
Klik dua kali file `run_app.bat` atau jalankan:
```bash
cd geo_photo_stamper
python main.py
```

### 3. Menjalankan Pengujian (Tests)
```bash
cd geo_photo_stamper
python tests/demo_overlay.py
python -m unittest tests/test_batch.py
```

---

## 📦 Membangun File Eksekusi (.exe) Mandiri

Untuk mendistribusikan aplikasi ke laptop tanpa Python terpasang:
```bash
cd geo_photo_stamper
pyinstaller --clean build.spec
```
File eksekusi `GeoPhotoStamper.exe` akan berada di dalam folder `dist/`.
