"""呼叫 ffmpeg／ffprobe。"""
from __future__ import annotations

import subprocess
from pathlib import Path

from critshowcase import tools


class ToolMissing(Exception):
    """找不到外部工具；訊息直接顯示給使用者。"""


class RenderError(Exception):
    """ffmpeg 執行失敗。"""


FFMPEG_HINT = "找不到 ffmpeg。請先安裝 ffmpeg（https://ffmpeg.org/download.html），並確認在命令列輸入 ffmpeg 可以執行。"


def require_ffmpeg() -> None:
    _tool("ffmpeg")
    _tool("ffprobe")


def _tool(name: str) -> str:
    path = tools.find(name)
    if path is None:
        raise ToolMissing(tools.missing_hint(name, FFMPEG_HINT))
    return path


def has_audio(path: Path) -> bool:
    result = subprocess.run(
        [_tool("ffprobe"), "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return bool(result.stdout.strip())


def duration(path: Path) -> float | None:
    result = subprocess.run(
        [_tool("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def run(args: list[str]) -> None:
    result = subprocess.run([_tool("ffmpeg"), "-y", "-v", "error", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RenderError(f"ffmpeg 失敗：{result.stderr.strip()[-2000:]}")
