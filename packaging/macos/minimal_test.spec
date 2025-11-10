# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for minimal database test app.
"""

import sys
from PyInstaller.utils.hooks import collect_all

a = Analysis(
    ['minimal_test_app.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['sqlite3'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MinimalDatabaseTest',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
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
    upx=True,
    upx_exclude=[],
    name='MinimalDatabaseTest',
)

app = BUNDLE(
    coll,
    name='MinimalDatabaseTest.app',
    icon=None,
    bundle_identifier=None,
)