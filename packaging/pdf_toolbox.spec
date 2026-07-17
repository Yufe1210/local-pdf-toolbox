# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata


root = Path(SPECPATH).parent
streamlit_datas, streamlit_binaries, streamlit_hiddenimports = collect_all("streamlit")
pdfium_datas, pdfium_binaries, pdfium_hiddenimports = collect_all("pypdfium2")
pdfium_raw_datas, pdfium_raw_binaries, pdfium_raw_hiddenimports = collect_all("pypdfium2_raw")
toolbox_hiddenimports = [
    module.strip()
    for module in (root / "packaging" / "required_toolbox_modules.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if module.strip()
]
update_config = Path(
    os.environ.get("PDF_TOOLBOX_UPDATE_CONFIG", str(root / "update-config.json"))
).resolve()
console_mode = os.environ.get("PDF_TOOLBOX_CONSOLE", "0") == "1"

datas = (
    streamlit_datas
    + pdfium_datas
    + pdfium_raw_datas
    + copy_metadata("pypdfium2")
    + [
    (str(root / "app.py"), "."),
    (str(update_config), "."),
    (
        str(root / "pdf_toolbox" / "ui" / "pdf_grid_frontend"),
        "pdf_toolbox/ui/pdf_grid_frontend",
    ),
    ]
)

a = Analysis(
    [str(root / "launcher.py")],
    pathex=[str(root)],
    binaries=streamlit_binaries + pdfium_binaries + pdfium_raw_binaries,
    datas=datas,
    hiddenimports=(
        streamlit_hiddenimports
        + pdfium_hiddenimports
        + pdfium_raw_hiddenimports
        + toolbox_hiddenimports
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="本機PDF工具箱",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=console_mode,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(root / "packaging" / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="本機PDF工具箱",
)
