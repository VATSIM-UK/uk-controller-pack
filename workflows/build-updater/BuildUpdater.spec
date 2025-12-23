import os

block_cipher = None

try:
    SPEC_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    SPEC_DIR = os.getcwd()

if os.path.isdir(os.path.join(SPEC_DIR, 'workflows', 'build-updater')):
    REPO_ROOT = SPEC_DIR
else:
    REPO_ROOT = os.path.dirname(SPEC_DIR)

def RR(*parts):
    return os.path.join(REPO_ROOT, *parts)

SCRIPT = RR('workflows', 'build-updater', 'Updater.py')
if not os.path.isfile(SCRIPT):
    raise SystemExit(f"[spec] Updater.py missing: {SCRIPT}")

datas = [(RR('workflows', 'build-updater', 'azure.tcl'), 'workflows/build-updater'),
        (RR('workflows', 'build-updater', 'logo.ico'),  'workflows/build-updater'),
]
theme_src = RR('workflows', 'build-updater', 'theme')
if os.path.isdir(theme_src):
    datas.append((theme_src, 'workflows/build-updater/theme'))

a = Analysis(
    [SCRIPT],
    pathex=[os.path.dirname(SCRIPT)],
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
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='Updater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=RR('workflows', 'build-updater', 'logo.ico'),
)
