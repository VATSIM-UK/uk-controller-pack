# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['LogonDetails.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('coastline1.png', '.'),
        ('coastline2.png', '.'),
        ('coastline3.png', '.'),
        ('land1.png', '.'),
        ('land2.png', '.'),
        ('land3.png', '.'),
        ('logo.ico', '.'),
        ('azure.tcl', '.')
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Configurator',
    icon='logo.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False  # Set to True if you want a visible terminal
)
