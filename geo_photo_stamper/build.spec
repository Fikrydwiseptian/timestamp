# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build specification for Geo Photo Stamper.
Menghasilkan file eksekusi Windows (.exe) mandiri tanpa console terminal.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Kumpulkan modul dan data tersembunyi
datas = [
    ('assets', 'assets'),
]
datas += collect_data_files('customtkinter')
datas += collect_data_files('tkinterdnd2')

hiddenimports = [
    'customtkinter',
    'tkinterdnd2',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'PIL.ImageOps',
    'piexif',
    'geopy',
    'geopy.geocoders',
    'geopy.geocoders.nominatim',
    'pillow_heif',
    'sqlite3',
    'requests',
]
hiddenimports += collect_submodules('geopy')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GeoPhotoStamper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
