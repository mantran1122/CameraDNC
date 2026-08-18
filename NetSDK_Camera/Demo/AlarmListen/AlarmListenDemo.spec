# -*- mode: python -*-
block_cipher = None
a = Analysis(['AlarmListenDemo.py' ],
                pathex = ['E:\jk_win7\workspace\CBB_DH3.RD003141_go_python_windows\code_path\Build_Stup/pack_temp'],
                binaries=[],
                datas=[],
				hiddenimports = [],
				hookspath = [],
				runtime_hooks = [],
				excludes = [],
				win_no_prefer_redirects = False,
				win_private_assemblies = False,
				cipher = block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='AlarmListenDemo',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False )
