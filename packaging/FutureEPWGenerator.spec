# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_all

project_root = Path(SPECPATH).resolve().parent

datas = [
    (str(project_root / "assets" / "app_icon.ico"), "assets"),
    (str(project_root / "assets" / "app_icon.png"), "assets"),
    (str(project_root / "assets" / "weather_catalog.json"), "assets"),
    (str(project_root / "engine_core"), "engine_core"),
    (str(project_root / "VERSION"), "."),
]
binaries = []
hiddenimports = []


def collect_conda_expat_runtime():
    """Collect Conda's Expat DLL when pyexpat depends on an external runtime."""
    roots = [
        Path(sys.prefix) / "Library" / "bin",
        Path(sys.prefix) / "DLLs",
        Path(sys.prefix),
    ]
    found = []
    seen = set()
    for root in roots:
        if not root.is_dir():
            continue
        for dll in sorted(root.glob("*expat*.dll")):
            resolved = str(dll.resolve())
            if resolved not in seen:
                found.append((resolved, "."))
                seen.add(resolved)
    return found


binaries += collect_conda_expat_runtime()
hiddenimports += ["pyexpat"]

# The scientific engine is executed from bundled source files at runtime, so
# explicitly collect its third-party runtime dependencies for the frozen app.
for package in [
    "numpy", "pandas", "numexpr", "xarray", "scipy", "zarr", "gcsfs",
    "s3fs", "cftime", "fsspec",
]:
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden


a = Analysis(
    [str(project_root / "app.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

gui_exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FutureEPWGenerator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(project_root / "assets" / "app_icon.ico"),
    version=str(project_root / "packaging" / "windows_version_info.txt"),
)

engine_exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FutureEPWEngine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=str(project_root / "assets" / "app_icon.ico"),
    version=str(project_root / "packaging" / "windows_version_info.txt"),
)

coll = COLLECT(
    gui_exe,
    engine_exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FutureEPWGenerator",
)
