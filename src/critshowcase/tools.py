"""找外部工具（ffmpeg、ffprobe、Deno）的路徑。

打包版（PyInstaller）把工具放在 exe 旁邊的 tools 資料夾，先找那裡、找不到才找 PATH；
用 pip 安裝時只找 PATH。
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def is_frozen() -> bool:
    """是不是打包成 exe 執行。"""
    return bool(getattr(sys, "frozen", False))


def find(name: str) -> str | None:
    """工具的完整路徑；找不到時回傳 None。"""
    if is_frozen():
        app = Path(sys.executable).parent
        bundled = shutil.which(name, path=os.pathsep.join([str(app / "tools"), str(app)]))
        if bundled:
            return bundled
    return shutil.which(name)


def missing_hint(name: str, pip_hint: str) -> str:
    """找不到工具時給使用者的訊息：pip 版教人安裝；打包版的工具本來就附在裡面，是解壓不完整。"""
    if not is_frozen():
        return pip_hint
    return f"critshowcase 安裝不完整，找不到 {name}。請重新解壓下載的 zip，整個資料夾一起使用（不要只複製 critshowcase.exe）。"
