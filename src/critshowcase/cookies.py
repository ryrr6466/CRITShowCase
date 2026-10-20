"""GUI 匯入的 cookies：使用者用瀏覽器擴充功能匯出的 cookies.txt，複製一份留著，之後出片都用它。

只存一份，放在 critshowcase 的使用者資料夾（Windows 是 %LOCALAPPDATA%\\critshowcase），不放在片段快取裡，
刪快取不會順便刪掉 cookies。只有 GUI 會用；CLI 仍要明確給 --cookies。
"""
from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from critshowcase.cache import default_cache_dir

FILENAME = "cookies.txt"


class CookieError(Exception):
    """這個檔案不能匯入。訊息直接顯示給使用者。"""


@dataclass(frozen=True)
class ImportedCookies:
    path: Path
    imported_at: datetime


def default_data_dir() -> Path:
    """片段快取的上一層：critshowcase 的使用者資料夾。"""
    return default_cache_dir().parent


class CookieStore:
    def __init__(self, folder: Path | None = None) -> None:
        self.folder = Path(folder) if folder else default_data_dir()

    @property
    def path(self) -> Path:
        return self.folder / FILENAME

    def current(self) -> ImportedCookies | None:
        """匯入時間就是那份檔案的修改時間（匯入時重新寫入）。"""
        try:
            modified = self.path.stat().st_mtime
        except OSError:
            return None
        return ImportedCookies(self.path, datetime.fromtimestamp(modified))

    def import_file(self, source: Path) -> ImportedCookies:
        """先確認是含 YouTube cookies 的 Netscape 格式檔案，才取代舊的；不能用的檔案不會蓋掉原本匯入的。"""
        _check(Path(source))
        self.folder.mkdir(parents=True, exist_ok=True)
        # 先複製成暫存檔再換上去，複製到一半失敗也不會留下壞掉的 cookies
        fd, staging = tempfile.mkstemp(prefix=".cookies-", dir=self.folder)
        os.close(fd)
        try:
            shutil.copyfile(source, staging)
            os.replace(staging, self.path)
        finally:
            Path(staging).unlink(missing_ok=True)
        current = self.current()
        assert current is not None
        return current

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)


def _check(source: Path) -> None:
    """用 yt-dlp 讀一次，確認出片時讀得了，而且裡面有 youtube.com 的 cookie。"""
    from http.cookiejar import LoadError

    from yt_dlp.cookies import YoutubeDLCookieJar

    if not source.is_file():
        raise CookieError(f"找不到 cookies 檔：{source}")
    jar = YoutubeDLCookieJar(str(source))
    try:
        jar.load()
    except (LoadError, UnicodeDecodeError, ValueError) as error:
        raise CookieError(f"{source.name} 不是 Netscape 格式的 cookies.txt（JSON 格式不行），請用瀏覽器擴充功能重新匯出。") from error
    except OSError as error:
        raise CookieError(f"讀不了 {source.name}：{error}") from error
    domains = {cookie.domain.lstrip(".") for cookie in jar}
    if not domains:
        raise CookieError(f"{source.name} 裡沒有任何 cookie。請確認是瀏覽器擴充功能匯出的 Netscape 格式 cookies.txt。")
    if not any(domain == "youtube.com" or domain.endswith(".youtube.com") for domain in domains):
        raise CookieError(
            f"{source.name} 裡沒有 youtube.com 的 cookies。"
            "匯出時要停在 YouTube 的網頁上（例如 youtube.com/robots.txt），匯出這個網站的 cookies。"
        )
