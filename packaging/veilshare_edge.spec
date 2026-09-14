# PyInstaller spec for the Windows build of VeilShare Edge.
#
# Build locally on Windows:
#   pip install -r requirements.txt pyinstaller
#   pyinstaller packaging/veilshare_edge.spec --noconfirm
#
# The .exe is produced at dist/VeilShareEdge/VeilShareEdge.exe (onedir build,
# recommended so startup stays fast — see docs/PACKAGING.md).
#
# This same spec is also run automatically on GitHub Actions for every push
# (see .github/workflows/build-windows.yml), so a fresh .exe is always
# available as a build artifact without requiring local Windows hardware.

import sys
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH).resolve().parents[0]

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "frontend"), "frontend"),
        (str(ROOT / "demo" / "sample_inputs"), "demo/sample_inputs"),
        (str(ROOT / "LICENSE"), "."),
        (str(ROOT / "README.md"), "."),
    ],
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
    ],
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
    [],
    exclude_binaries=True,
    name="VeilShareEdge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="VeilShareEdge",
)
