# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['waitress', 'psycopg2', 'psycopg2_binary']
hiddenimports += collect_submodules('training_center')
hiddenimports += collect_submodules('trainees')
hiddenimports += collect_submodules('core')
hiddenimports += collect_submodules('sync_core')
hiddenimports += collect_submodules('django')


a = Analysis(
    ['G:\\training_center_ar_v2_1\\launcher\\lan_server.py'],
    pathex=['G:\\training_center_ar_v2_1'],
    binaries=[],
    datas=[('G:\\training_center_ar_v2_1\\templates', 'templates'), ('G:\\training_center_ar_v2_1\\core', 'core'), ('G:\\training_center_ar_v2_1\\trainees', 'trainees'), ('G:\\training_center_ar_v2_1\\sync_core', 'sync_core'), ('G:\\training_center_ar_v2_1\\training_center', 'training_center'), ('G:\\training_center_ar_v2_1\\.env.lan.example', '.'), ('G:\\training_center_ar_v2_1\\.env.example', '.'), ('G:\\training_center_ar_v2_1\\INSFP.jpg', '.'), ('G:\\training_center_ar_v2_1\\mfep.ico', '.')],
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
    a.binaries,
    a.datas,
    [],
    name='TrainingCenterOfficeServer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['G:\\training_center_ar_v2_1\\mfep.ico'],
)
