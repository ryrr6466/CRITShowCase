# PyInstaller spec：onedir、保留 console（錯誤訊息要看得到）。由 packaging/build.py 呼叫。
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

root = Path(SPECPATH).parent

a = Analysis(
    [str(root / "src" / "critshowcase" / "__main__.py")],
    pathex=[str(root / "src")],
    # --version 從套件的 metadata 讀版本
    datas=copy_metadata("critshowcase") + copy_metadata("yt-dlp"),
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="critshowcase", console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="critshowcase")
