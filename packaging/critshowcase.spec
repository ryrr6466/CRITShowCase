# PyInstaller spec：onedir 裡兩個 exe，共用依賴與 tools 資料夾。由 packaging/build.py 呼叫。
# critshowcase.exe 保留 console（拖放與命令列，錯誤訊息要看得到）；critshowcase-gui.exe 是沒有 console 的視窗程式。
# macOS 另外包成 CRITShowCase.app：GUI 是 app 的主程式，命令列版放在同一個 Contents/MacOS。
import sys
from importlib.metadata import version
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

root = Path(SPECPATH).parent
macos = sys.platform == "darwin"

datas = (
    # --version 與 GUI 從套件的 metadata 讀版本
    copy_metadata("critshowcase") + copy_metadata("yt-dlp")
    # yt-dlp 解 YouTube 驗證題的 JS（yt-dlp 自帶的 hook 也會收，這裡寫明，不靠上游）
    + collect_data_files("yt_dlp_ejs", includes=["**/*.js"])
)
a = Analysis([str(root / "src" / "critshowcase" / "__main__.py")], pathex=[str(root / "src")], datas=datas)
# GUI 另外分析：tkinter 與 Tcl／Tk 的資料只有它會收進來；字標與視窗 icon 也只有它用
gui_datas = datas + [(str(root / "src" / "critshowcase" / "gui" / "assets" / "*.png"), "critshowcase/gui/assets")]
gui = Analysis([str(root / "src" / "critshowcase" / "gui" / "__main__.py")], pathex=[str(root / "src")], datas=gui_datas)
# 檔案總管裡 exe 的圖示：CRITLOG App icon（macOS 的圖示在下面的 BUNDLE）
icon = None if macos else str(root / "packaging" / "critshowcase.ico")
exe = EXE(PYZ(a.pure), a.scripts, [], exclude_binaries=True, name="critshowcase", console=True, icon=icon)
gui_exe = EXE(PYZ(gui.pure), gui.scripts, [], exclude_binaries=True, name="critshowcase-gui", console=False, icon=icon)

if not macos:
    coll = COLLECT(exe, gui_exe, a.binaries, a.datas, gui.binaries, gui.datas, name="critshowcase")
else:
    # BUNDLE 把 TOC 裡第一個執行檔當成 app 的主程式，所以 GUI 放前面
    coll = COLLECT(gui_exe, exe, gui.binaries, gui.datas, a.binaries, a.datas, name="critshowcase")
    current = version("critshowcase")
    app = BUNDLE(
        coll,
        name="CRITShowCase.app",
        icon=str(root / "packaging" / "critshowcase.icns"),
        bundle_identifier="me.critlog.showcase",
        version=current,
        info_plist={
            "CFBundleDisplayName": "CRITShowCase",
            "CFBundleShortVersionString": current,
            "CFBundleVersion": current,
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
            # 可以把影片專案拖到 app 圖示上；Alternate：不搶走 zip、json 原本的預設開啟程式
            "CFBundleDocumentTypes": [
                {
                    "CFBundleTypeName": "CRITShowCase 影片專案",
                    "CFBundleTypeRole": "Viewer",
                    "LSHandlerRank": "Alternate",
                    "LSItemContentTypes": ["public.zip-archive", "public.json"],
                }
            ],
        },
    )
