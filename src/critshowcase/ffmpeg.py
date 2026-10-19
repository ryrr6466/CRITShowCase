"""呼叫 ffmpeg／ffprobe。"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class ToolMissing(Exception):
    """找不到外部工具；訊息直接顯示給使用者。"""


class RenderError(Exception):
    """ffmpeg 執行失敗。"""


FFMPEG_HINT ="找不到 ffmpeg。請先安裝 ffmpeg（https://ffmpeg.org/download.html），並確認在命令列輸入 ffmpeg 可以執行。"


def require_ffmpeg() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise ToolMissing(FFMPEG_HINT)


def has_audio(path: Path) -> bool:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return bool(result.stdout.strip())


def run(args: list[str]) -> None:
    result = subprocess.run(["ffmpeg", "-y", "-v", "error", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RenderError(f"ffmpeg 失敗：{result.stderr.strip()[-2000:]}")
