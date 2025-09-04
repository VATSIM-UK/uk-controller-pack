import os
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.building.datastruct import Tree

block_cipher = None

try:
    SPEC_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    SPEC_DIR = os.getcwd()

PROJECT_ROOT = SPEC_DIR

def R(*parts):
    return os.path.join(PROJECT_ROOT, *parts)

datas = [
    (R('workflows', 'build-updater', 'azure.tcl'), 'workflows/build-updater'),
]

theme_src = R('workflows', 'build-updater', 'theme')
if os.path.isdir(theme_src):
    datas.append(Tree(theme_src, prefix='workflows/build-updater/theme'))

a = Analysis(
    ['Updater.py'],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=[],
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
    name='Updater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # change to True if UPX is installed
    console=False,
    icon=R('workflows', 'build-updater', 'logo.ico')
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Updater'
)