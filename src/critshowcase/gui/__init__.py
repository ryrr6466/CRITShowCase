"""GUI 進入點：critshowcase-gui [影片專案]。

tkinter 在這裡才載入：有些 Python（例如 Linux 套件管理員裝的）沒有附 Tk，要能說明原因後結束，而不是直接 ImportError。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 免安裝版的煙霧測試用：視窗開起來後自己關掉，確認 exe 帶齊了 Tcl／Tk、建得出視窗
SMOKE_ENV = "CRITSHOWCASE_GUI_SMOKE"
SMOKE_MS = 1000

NO_TKINTER = (
    "critshowcase-gui：這個 Python 沒有 tkinter，打不開視窗。\n"
    "Linux 請安裝 python3-tk（例如 sudo apt install python3-tk）；macOS 請改用 python.org 的安裝程式裝 Python。\n"
    "也可以改用命令列：critshowcase <影片專案 zip>"
)


def main(argv: list[str] | None = None) -> int:
    """第一個參數（拖到 exe 圖示上的檔案）預先填入影片專案。"""
    args = sys.argv[1:] if argv is None else argv
    try:
        import tkinter
    except ImportError:
        _error(NO_TKINTER)
        return 1
    try:
        root = tkinter.Tk()
    except tkinter.TclError as error:
        _error(f"critshowcase-gui：打不開視窗：{error}")
        return 1
    from critshowcase.gui.app import App

    App(root, source=Path(args[0]) if args else None)
    if os.environ.get(SMOKE_ENV):
        root.after(SMOKE_MS, root.destroy)
    root.mainloop()
    return 0


def _error(message: str) -> None:
    # 打包版的 GUI 沒有 console，sys.stderr 是 None
    if sys.stderr is not None:
        print(message, file=sys.stderr)
