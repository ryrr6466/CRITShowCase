"""出片工作：載入影片專案 → 下載片段 → 合成 mp4。CLI 與 GUI 共用，自己不印任何東西。

打包版的 GUI 沒有 console，sys.stdout／sys.stderr 可能是 None；訊息一律放在結果與進度事件裡，由介面決定怎麼顯示。
"""
from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from critshowcase import tools
from critshowcase.cache import CachedDownloader, default_cache_dir
from critshowcase.download import RELEASES, DownloadBlocked, Downloader, YtDlpDownloader
from critshowcase.ffmpeg import RenderError, ToolMissing
from critshowcase.project import ProjectError, load_project
from critshowcase.render import Failure, Progress, render

EXIT_OK = 0
EXIT_ERROR = 1
# 影片輸出了，但有片段下載失敗、改成靜態畫面
EXIT_PARTIAL = 3

UPDATE_HINT = f"所有片段都下載失敗，可能是 YouTube 改版了。請到 {RELEASES} 下載最新版 critshowcase 後再試。"


@dataclass
class JobResult:
    """output 是成品路徑（沒有輸出時是 None）；error 是沒有輸出的原因，訊息直接顯示給使用者。"""

    output: Path | None = None
    failures: list[Failure] = field(default_factory=list)
    error: str | None = None
    # 讀不到 cookies 或 YouTube 要求登入驗證：介面可以引導使用者處理 cookies
    blocked: bool = False
    # 一個片段都下載不到，而且是打包版：多半是 YouTube 改版、yt-dlp 跟不上，使用者沒辦法自己更新 yt-dlp
    update_hint: str | None = None

    @property
    def exit_code(self) -> int:
        if self.output is None:
            return EXIT_ERROR
        return EXIT_PARTIAL if self.failures else EXIT_OK


def default_output(source: Path) -> Path:
    """成品預設放在輸入檔旁邊。"""
    return Path(source).with_suffix(".mp4")


def run_job(
    source: Path,
    output: Path | None = None,
    *,
    cookies_from_browser: str | None = None,
    cookies: Path | None = None,
    refresh: bool = False,
    verbose: bool = False,
    downloader: Downloader | None = None,
    progress: Callable[[Progress], None] | None = None,
) -> JobResult:
    """downloader 給測試注入；沒給時影片專案有片段才建立有快取的 yt-dlp 下載器。"""
    source = Path(source)
    output = Path(output) if output else default_output(source)
    if not source.is_file():
        return JobResult(error=f"找不到檔案 {source}")
    try:
        with tempfile.TemporaryDirectory(prefix="critshowcase-") as tmp:
            project = load_project(source, workdir=Path(tmp) / "project")
            if downloader is None and any(segment.clip for segment in project.segments):
                downloader = CachedDownloader(
                    YtDlpDownloader(cookies_from_browser, cookies, workdir=Path(tmp), verbose=verbose),
                    default_cache_dir(),
                    refresh=refresh,
                )
            report = render(project, output, downloader=downloader, workdir=Path(tmp), progress=progress)
    except DownloadBlocked as error:
        return JobResult(error=str(error), blocked=True)
    except (ProjectError, ToolMissing, RenderError) as error:
        return JobResult(error=str(error))
    result = JobResult(output=output, failures=report.failures)
    if tools.is_frozen() and report.failures and len(report.failures) == sum(1 for segment in project.segments if segment.clip):
        result.update_hint = UPDATE_HINT
    return result
