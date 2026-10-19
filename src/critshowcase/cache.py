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
        # 用浮點數的完整表示，差 1 毫秒也是不同的片段
        key = f"{clip.youtube_id}_{float(clip.start)!r}_{float(seconds)!r}"
        hit = self._find(key)
        if hit and not self.refresh:
            return hit
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=".partial-", dir=self.cache_dir))
        except OSError:
            # 快取資料夾不能用（例如是系統管理員身分建立的）：這次不存快取，照樣下載
            return self.inner.fetch(clip, seconds, dest)
        # 先下載到快取裡的暫存資料夾，完整下載完才改名成正式檔名；中斷的下載不會被當成快取
        try:
            downloaded = self.inner.fetch(clip, seconds, staging)
            try:
                for old in self._matches(key):
                    old.unlink()
                final = self.cache_dir / f"{key}{downloaded.suffix}"
                os.replace(downloaded, final)
                return final
            except OSError:
                # 舊的快取檔刪不掉或蓋不過：片段改放到這次執行的資料夾
                return Path(shutil.move(downloaded, Path(dest) / downloaded.name))
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _find(self, key: str) -> Path | None:
        """讀得到的快取檔才算命中：別的使用者或系統管理員身分留下的檔案可能讀不了。"""
        for path in self._matches(key):
            try:
                with path.open("rb") as file:
                    file.read(1)
            except OSError:
                continue
            return path
        return None

    def _matches(self, key: str) -> list[Path]:
        if not self.cache_dir.is_dir():
            return []
        # 比對完整的主檔名：10 秒的 key 不能誤中 10.5 秒的檔案
        return [path for path in self.cache_dir.glob(f"{key}.*") if path.is_file() and path.stem == key]
