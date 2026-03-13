# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

added_files = [
    ('app/templates', 'app/templates'),
    ('raptorcast_v4_guilin.py', '.'),
    ('.env', '.'),
]

# 隐藏导入，确保所有依赖都被正确打包
hidden_imports = [
    'openmeteo_requests',
    'requests_cache',
    'retry_requests',
    'dotenv',
    'numpy',
]

a = Analysis(['app/app.py'],
             pathex=['.'],
             binaries=[],
             datas=added_files,
             hiddenimports=hidden_imports,
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='falcon_forecast',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True,
          icon=None)
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='falcon_forecast')