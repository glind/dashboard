# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app_main_simple.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['requests', 'webview', 'webbrowser'],
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
    name='Personal Dashboard',
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
    icon=['buildly_icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Personal Dashboard',
)
app = BUNDLE(
    coll,
    name='Personal Dashboard.app',
    icon='buildly_icon.icns',
    bundle_identifier=None,
)
