"""片段快取：依（影片 ID、開始秒數、長度）存下載過的片段，重跑時不再下載。

改一段評論就要重新匯出、重新出片（ADR 0001 的後果），沒有快取的話每次都要重抓全部片段。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

from critshowcase.download import Downloader
from critshowcase.project import Clip


def default_cache_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "critshowcase" / "clips"


class CachedDownloader:
    def __init__(self, inner: Downloader, cache_dir: Path, refresh: bool = False) -> None:
        """refresh=True 時一律重新下載，並換掉快取裡的舊檔。"""
        self.inner = inner
        self.cache_dir = Path(cache_dir)
        self.refresh = refresh

    def fetch(self, clip: Clip, seconds: float, dest: Path) -> Path:
        key = f"{clip.youtube_id}_{clip.start:g}_{seconds:g}"
        hit = self._find(key)
        if hit and not self.refresh:
            return hit
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # 先下載到快取裡的暫存資料夾，完整下載完才改名成正式檔名；中斷的下載不會被當成快取
        staging = Path(tempfile.mkdtemp(prefix=".partial-", dir=self.cache_dir))
        try:
            downloaded = self.inner.fetch(clip, seconds, staging)
            for old in self._matches(key):
                old.unlink()
            final = self.cache_dir / f"{key}{downloaded.suffix}"
            os.replace(downloaded, final)
            return final
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _find(self, key: str) -> Path | None:
        return next(iter(self._matches(key)), None)

    def _matches(self, key: str) -> list[Path]:
        if not self.cache_dir.is_dir():
            return []
        # 比對完整的主檔名：10 秒的 key 不能誤中 10.5 秒的檔案
        return [path for path in self.cache_dir.glob(f"{key}.*") if path.is_file() and path.stem == key]
