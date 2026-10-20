# PyInstaller spec：onedir 裡兩個 exe，共用依賴與 tools 資料夾。由 packaging/build.py 呼叫。
# critshowcase.exe 保留 console（拖放與命令列，錯誤訊息要看得到）；critshowcase-gui.exe 是沒有 console 的視窗程式。
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

root = Path(SPECPATH).parent

datas = (
    # --version 與 GUI 從套件的 metadata 讀版本
    copy_metadata("critshowcase") + copy_metadata("yt-dlp")
    # yt-dlp 解 YouTube 驗證題的 JS（yt-dlp 自帶的 hook 也會收，這裡寫明，不靠上游）
    + collect_data_files("yt_dlp_ejs", includes=["**/*.js"])
)
a = Analysis([str(root / "src" / "critshowcase" / "__main__.py")], pathex=[str(root / "src")], datas=datas)
# GUI 另外分析：tkinter 與 Tcl／Tk 的資料只有它會收進來
gui = Analysis([str(root / "src" / "critshowcase" / "gui" / "__main__.py")], pathex=[str(root / "src")], datas=datas)
exe = EXE(PYZ(a.pure), a.scripts, [], exclude_binaries=True, name="critshowcase", console=True)
gui_exe = EXE(PYZ(gui.pure), gui.scripts, [], exclude_binaries=True, name="critshowcase-gui", console=False)
coll = COLLECT(exe, gui_exe, a.binaries, a.datas, gui.binaries, gui.datas, name="critshowcase")
