# PyInstaller spec：onedir、保留 console（錯誤訊息要看得到）。由 packaging/build.py 呼叫。
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

root = Path(SPECPATH).parent

a = Analysis(
    [str(root / "src" / "critshowcase" / "__main__.py")],
    pathex=[str(root / "src")],
    datas=(
        # --version 從套件的 metadata 讀版本
        copy_metadata("critshowcase") + copy_metadata("yt-dlp")
        # yt-dlp 解 YouTube 驗證題的 JS（yt-dlp 自帶的 hook 也會收，這裡寫明，不靠上游）
        + collect_data_files("yt_dlp_ejs", includes=["**/*.js"])
    ),
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="critshowcase", console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="critshowcase")
