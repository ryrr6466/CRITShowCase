"""下載片段：只抓 [start, start + seconds] 這一段（spec §8.3）。"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Protocol

from critshowcase import tools
from critshowcase.ffmpeg import ToolMissing
from critshowcase.project import Clip

YT_DLP_HINT = "找不到 yt-dlp。請執行 pip install -U \"yt-dlp[default]\" 後再試。"
RELEASES = "https://github.com/ryrr6466/CRITShowCase/releases"
ANSI = re.compile(r"\x1b\[[0-9;]*m")
SITE_PREFIX = re.compile(r"^\[[\w:]+\] [\w-]+: ")


class DownloadError(Exception):
    """這個片段下載不到（影片本身的問題）；該段改成靜態畫面。訊息直接顯示給使用者。"""


class DownloadBlocked(Exception):
    """整台電腦都下載不了（讀不到 cookies、YouTube 要求登入驗證），中斷整支影片。訊息直接顯示給使用者。"""


class Downloader(Protocol):
    def fetch(self, clip: Clip, seconds: float, dest: Path) -> Path:
        """把片段的那一段存進 dest 資料夾，回傳檔案路徑；檔案從 0 秒開始就是 clip.start 的畫面。"""
        ...


class _YtDlpLogger:
    """錯誤一律透過例外回報；yt-dlp 自己的訊息只在 --verbose 時印出來（除錯用）。"""

    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose

    def _print(self, message: str) -> None:
        if self.verbose:
            print(f"[yt-dlp] {_clean(message)}", file=sys.stderr, flush=True)

    def debug(self, message: str) -> None:
        self._print(message)

    def info(self, message: str) -> None:
        self._print(message)

    def warning(self, message: str) -> None:
        self._print(message)

    def error(self, message: str) -> None:
        self._print(message)


class YtDlpDownloader:
    def __init__(
        self,
        cookies_from_browser: str | None = None,
        cookies: Path | None = None,
        workdir: Path | None = None,
        verbose: bool = False,
    ) -> None:
        """YouTube 要求登入驗證時，用瀏覽器的 cookies（例如 "firefox"）或匯出的 cookies.txt。

        瀏覽器的 cookies 在這裡先讀一次、存成 workdir 裡的 cookies.txt（workdir 由呼叫端負責刪除），
        讀不到就立刻丟 DownloadBlocked，不必等到下載第一個片段，也不必每個片段都再讀一次瀏覽器。
        """
        try:
            import yt_dlp  # noqa: F401
        except ImportError as error:
            raise ToolMissing(tools.incomplete_install("yt-dlp") if tools.is_frozen() else YT_DLP_HINT) from error
        self.verbose = verbose
        self.uses_cookies = bool(cookies_from_browser or cookies)
        self.cookie_file = cookies
        if cookies_from_browser:
            if workdir is None:
                raise ValueError("使用瀏覽器的 cookies 時要給 workdir")
            self.cookie_file = _export_browser_cookies(cookies_from_browser, Path(workdir) / "cookies.txt", verbose)
        elif cookies:
            _check_cookie_file(cookies, verbose)

    def fetch(self, clip: Clip, seconds: float, dest: Path) -> Path:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import YoutubeDLError, download_range_func

        options = {
            # 1080p 以內畫質最好的影像＋聲音
            "format": "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b",
            # 同一支影片可能在不同段落用不同範圍，檔名要帶上範圍
            "outtmpl": str(Path(dest) / f"{clip.youtube_id}_{float(clip.start)!r}_{float(seconds)!r}.%(ext)s"),
            "download_ranges": download_range_func(None, [(clip.start, clip.start + seconds)]),
            # 在切點補關鍵格，片段才會剛好從 start 開始
            "force_keyframes_at_cuts": True,
            "merge_output_format": "mkv",
            **_tool_options(),
            "logger": _YtDlpLogger(self.verbose),
            "verbose": self.verbose,
            "noprogress": True,
        }
        if self.cookie_file:
            options["cookiefile"] = str(self.cookie_file)
        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={clip.youtube_id}", download=True)
        except YoutubeDLError as error:
            message = _clean(str(error))
            if "not a bot" in message.lower():
                raise DownloadBlocked(_bot_check_hint(self.uses_cookies)) from error
            raise DownloadError(_reason(message)) from error
        downloads = (info or {}).get("requested_downloads") or []
        path = Path(downloads[0]["filepath"]) if downloads else None
        if path is None or not path.is_file():
            raise DownloadError("下載完成但找不到檔案")
        return path


def update_hint() -> str:
    """YouTube 改版時 yt-dlp 要更新；打包版的使用者沒辦法自己更新，要下載新版。"""
    if tools.is_frozen():
        return f"請到 {RELEASES} 下載最新版 critshowcase 後再試。"
    return '請執行 pip install -U "yt-dlp[default]" 更新 yt-dlp 後再試。'


def _tool_options() -> dict[str, object]:
    """打包版的 ffmpeg、Deno 在 exe 旁邊，yt-dlp 自己找不到，要明確告訴它。"""
    options: dict[str, object] = {}
    ffmpeg = tools.find("ffmpeg")
    if ffmpeg:
        # 給資料夾，yt-dlp 才會在同一處找 ffprobe
        options["ffmpeg_location"] = str(Path(ffmpeg).parent)
    # 解 YouTube 驗證題要 JS 執行環境（yt-dlp-ejs）；Deno 或 Node 有一個就好
    deno = tools.find("deno")
    options["js_runtimes"] = {"deno": {"path": deno}} if deno else {"deno": {}, "node": {}}
    return options


def _export_browser_cookies(browser: str, target: Path, verbose: bool) -> Path:
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import YoutubeDLError

    try:
        with YoutubeDL({"cookiesfrombrowser": (browser,), "logger": _YtDlpLogger(verbose)}) as ydl:
            target.parent.mkdir(parents=True, exist_ok=True)
            ydl.cookiejar.save(str(target))
    except (YoutubeDLError, OSError, ValueError) as error:
        raise DownloadBlocked(_cookie_hint(browser, _clean(str(error)))) from error
    return target


def _check_cookie_file(path: Path, verbose: bool) -> None:
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import YoutubeDLError

    if not Path(path).is_file():
        raise DownloadBlocked(f"找不到 cookies 檔：{path}")
    try:
        with YoutubeDL({"cookiefile": str(path), "logger": _YtDlpLogger(verbose)}) as ydl:
            ydl.cookiejar
    except (YoutubeDLError, OSError) as error:
        raise DownloadBlocked(f"讀不了 cookies 檔 {path}：{_clean(str(error))}。請確認是 Netscape 格式的 cookies.txt。") from error


def _cookie_hint(browser: str, message: str) -> str:
    if "could not copy chrome cookie database" in message.lower():
        return (
            f"讀不到 {browser} 的 cookies：Windows 上的 Edge／Chrome 開著時會鎖住 cookie 資料庫。"
            f"請完全關閉 {browser}（包含背景執行的程序）後再試；還是不行的話，改用 --cookies-from-browser firefox，"
            "或用瀏覽器擴充功能匯出 cookies.txt 後改用 --cookies cookies.txt。"
        )
    return f"讀不到 {browser} 的 cookies：{message}"


def _bot_check_hint(uses_cookies: bool) -> str:
    if uses_cookies:
        return "YouTube 要求登入驗證，用了 cookies 仍然被擋。請確認那個瀏覽器已經登入 YouTube，或重新匯出 cookies 後再試。"
    return "YouTube 要求登入驗證，這台電腦目前無法下載。請加上 --cookies-from-browser firefox（換成你登入 YouTube 的瀏覽器）再試。"


def _clean(message: str) -> str:
    """拿掉 yt-dlp 訊息裡的顏色碼、重複的 ERROR: 前綴與 [youtube] <id>: 前綴。"""
    message = ANSI.sub("", message).strip()
    while message.startswith("ERROR:"):
        message = message.removeprefix("ERROR:").strip()
    return SITE_PREFIX.sub("", message)


def _reason(message: str) -> str:
    """把 yt-dlp 的錯誤換成使用者看得懂的說法。"""
    lowered = message.lower()
    if "private video" in lowered:
        return "影片設成私人"
    if "video unavailable" in lowered or "has been removed" in lowered:
        return "影片已刪除或無法觀看"
    if "not available in your country" in lowered or "geo restrict" in lowered:
        return "影片在你的地區無法觀看"
    if "sign in to confirm your age" in lowered:
        return "影片有年齡限制"
    if "unable to download" in lowered or "timed out" in lowered or "connection" in lowered:
        return "網路錯誤"
    return message
