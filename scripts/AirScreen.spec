# -*- mode: python ; coding: utf-8 -*-
# Portable PyInstaller spec. Build from the repo root:  pyinstaller scripts/AirScreen.spec --noconfirm
import os
from PyInstaller.utils.hooks import collect_submodules, collect_all

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
datas = [(os.path.join(ROOT, "sender", "airscreen_sender", "webui"), "airscreen_sender/webui")]
binaries = []
hiddenimports = ["cryptography.hazmat.primitives.asymmetric.ec"] + collect_submodules("zeroconf")
for pkg in ("dxcam", "pyaudiowpatch", "pycaw", "comtypes"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

a = Analysis(
    [os.path.join(ROOT, "sender", "airscreen_app.py")],
    pathex=[os.path.join(ROOT, "sender")],
    binaries=binaries, datas=datas, hiddenimports=hiddenimports,
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="AirScreen",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False,
    disable_windowed_traceback=False, argv_emulation=False, target_arch=None,
    codesign_identity=None, entitlements_file=None,
    icon=[os.path.join(ROOT, "assets", "branding", "AirScreen.ico")],
    version=os.path.join(ROOT, "scripts", "version_info.txt"),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="AirScreen")
