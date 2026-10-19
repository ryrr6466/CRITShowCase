"""下載片段：只抓 [start, start + seconds] 這一段（spec §8.3）。"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from critshowcase.ffmpeg import ToolMissing
from critshowcase.project import Clip

YT_DLP_HINT = "找不到 yt-dlp。請執行 pip install -U yt-dlp 後再試。"


class DownloadError(Exception):
    """這個片段下載不到；訊息直接顯示給使用者。"""


class Downloader(Protocol):
    def fetch(self, clip: Clip, seconds: float, dest: Path) -> Path:
        """把片段的那一段存進 dest 資料夾，回傳檔案路徑；檔案從 0 秒開始就是 clip.start 的畫面。"""
        ...


class YtDlpDownloader:
    def __init__(self, cookies_from_browser: str | None = None, cookies: Path | None = None) -> None:
        """YouTube 要求登入驗證時，用瀏覽器的 cookies（例如 "firefox"）或匯出的 cookies.txt。"""
        try:
            import yt_dlp  # noqa: F401
        except ImportError as error:
            raise ToolMissing(YT_DLP_HINT) from error
        self.cookies_from_browser = cookies_from_browser
        self.cookies = cookies

    def fetch(self, clip: Clip, seconds: float, dest: Path) -> Path:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError as YtDlpError
        from yt_dlp.utils import download_range_func

        options = {
            # 1080p 以內畫質最好的影像＋聲音
            "format": "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b",
            "outtmpl": str(Path(dest) / f"{clip.youtube_id}-{clip.start:g}-{seconds:g}.%(ext)s"),
            "download_ranges": download_range_func(None, [(clip.start, clip.start + seconds)]),
            # 在切點補關鍵格，片段才會剛好從 start 開始
            "force_keyframes_at_cuts": True,
            "merge_output_format": "mkv",
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
        }
        if self.cookies_from_browser:
            options["cookiesfrombrowser"] = (self.cookies_from_browser,)
        if self.cookies:
            options["cookiefile"] = str(self.cookies)
        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={clip.youtube_id}", download=True)
        except YtDlpError as error:
            raise DownloadError(_reason(str(error))) from error
        downloads = (info or {}).get("requested_downloads") or []
        path = Path(downloads[0]["filepath"]) if downloads else None
        if path is None or not path.is_file():
            raise DownloadError("下載完成但找不到檔案")
        return path


def _reason(message: str) -> str:
    """把 yt-dlp 的錯誤換成使用者看得懂的說法。"""
    lowered = message.lower()
    if "not a bot" in lowered:
        return "YouTube 要求登入驗證，請加上 --cookies-from-browser（例如 --cookies-from-browser firefox）再試"
    if "private video" in lowered:
        return "影片設成私人"
    if "video unavailable" in lowered or "has been removed" in lowered:
        return "影片已刪除或無法觀看"
    if "not available in your country" in lowered or "geo" in lowered:
        return "影片在你的地區無法觀看"
    if "sign in to confirm your age" in lowered:
        return "影片有年齡限制"
    if "unable to download" in lowered or "timed out" in lowered or "connection" in lowered:
        return "網路錯誤"
    return message.removeprefix("ERROR: ").strip()
