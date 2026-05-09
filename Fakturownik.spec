from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path(SPECPATH)
hiddenimports = collect_submodules("fakturownik")
brand_icon = project_root / "src" / "fakturownik" / "assets" / "app_icon.ico"


a = Analysis(
    [str(project_root / "app.py")],
    pathex=[str(project_root), str(project_root / "src")],
    binaries=[],
    datas=[
        (str(project_root / "src" / "fakturownik" / "assets" / "app_icon.ico"), "fakturownik/assets"),
        (str(project_root / "src" / "fakturownik" / "assets" / "app_icon.png"), "fakturownik/assets"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Fakturownik",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=str(brand_icon),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Fakturownik",
)