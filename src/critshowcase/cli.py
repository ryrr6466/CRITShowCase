"""命令列介面：critshowcase <zip 或 project.json>。"""
from __future__ import annotations

import argparse
import sys
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from critshowcase import tools
from critshowcase.cache import CachedDownloader, default_cache_dir
from critshowcase.download import RELEASES, DownloadBlocked, Downloader, YtDlpDownloader
from critshowcase.ffmpeg import RenderError, ToolMissing
from critshowcase.project import ProjectError, load_project
from critshowcase.render import render

EXIT_ERROR = 1
# 影片輸出了，但有片段下載失敗、改成靜態畫面
EXIT_PARTIAL = 3


USAGE_FOR_DRAG_AND_DROP = (
    "critshowcase：把 CRITShowCase 頁面匯出的影片專案 zip 拖到 critshowcase.exe 上，就會開始出片。\n"
    "成品會放在 zip 旁邊。進階選項請在命令列執行 critshowcase.exe --help。"
)


def main(argv: list[str] | None = None, downloader: Downloader | None = None) -> int:
    """downloader 給測試注入；沒給時影片專案有片段才建立 yt-dlp 下載器。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    # 拖放或雙擊啟動時，console 是為這次執行開的，結束就會關掉：先停住讓人看結果
    pause = _owns_console()
    try:
        if pause and not (sys.argv[1:] if argv is None else argv):
            print(USAGE_FOR_DRAG_AND_DROP, file=sys.stderr)
            return EXIT_ERROR
        return _run(argv, downloader)
    finally:
        if pause:
            _wait_for_enter()


def _run(argv: list[str] | None, downloader: Downloader | None) -> int:
    args = _parser().parse_args(argv)
    source = Path(args.input)
    output = Path(args.output) if args.output else _default_output(source)
    if not source.is_file():
        print(f"critshowcase：找不到檔案 {source}", file=sys.stderr)
        return EXIT_ERROR
    try:
        with tempfile.TemporaryDirectory(prefix="critshowcase-") as tmp:
            project = load_project(source, workdir=Path(tmp) / "project")
            if downloader is None and any(segment.clip for segment in project.segments):
                downloader = CachedDownloader(
                    YtDlpDownloader(
                        args.cookies_from_browser,
                        Path(args.cookies) if args.cookies else None,
                        workdir=Path(tmp),
                        verbose=args.verbose,
                    ),
                    default_cache_dir(),
                    refresh=args.refresh,
                )
            report = render(project, output, downloader=downloader, workdir=Path(tmp), progress=lambda message: print(message, flush=True))
    except (ProjectError, ToolMissing, RenderError, DownloadBlocked) as error:
        print(f"critshowcase：{error}", file=sys.stderr)
        return EXIT_ERROR
    print(f"完成：{output}")
    if report.failures:
        print(f"\n有 {len(report.failures)} 個片段下載失敗，這些段落改成靜態畫面：", file=sys.stderr)
        for failure in report.failures:
            print(f"  第 {failure.position} 段  {failure.youtube_id}  {failure.reason}", file=sys.stderr)
        print("可以回 CRITShowCase 頁面換掉這些片段，重新匯出後再執行一次。", file=sys.stderr)
        if tools.is_frozen() and len(report.failures) == sum(1 for segment in project.segments if segment.clip):
            # 一個都下載不到，多半是 YouTube 改版、yt-dlp 跟不上；打包版的使用者沒辦法自己更新 yt-dlp
            print(f"所有片段都下載失敗，可能是 YouTube 改版了。請到 {RELEASES} 下載最新版 critshowcase 後再試。", file=sys.stderr)
        return EXIT_PARTIAL
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="critshowcase",
        description="把 CRITShowCase（B50 影片）匯出的影片專案合成 mp4。",
    )
    parser.add_argument("--version", action=_VersionAction, nargs=0, help="印出 critshowcase 與 yt-dlp 的版本後結束")
    parser.add_argument("input", help="網頁匯出的 zip，或解開後的 project.json")
    parser.add_argument("-o", "--output", help="輸出的 mp4 路徑（預設放在輸入檔旁邊）")
    parser.add_argument("--cookies-from-browser", metavar="BROWSER", help="YouTube 要求登入驗證時，使用這個瀏覽器的 cookies（例如 firefox、chrome）")
    parser.add_argument("--cookies", metavar="FILE", help="YouTube 要求登入驗證時，使用匯出的 cookies.txt")
    parser.add_argument("--verbose", action="store_true", help="印出 yt-dlp 的詳細訊息（下載失敗時除錯用）")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help=f"不用快取，所有片段重新下載（快取在 {default_cache_dir()}，可以直接刪除）",
    )
    return parser


def _owns_console() -> bool:
    """打包版從檔案總管啟動（拖放、雙擊）：console 只有自己在用。從 cmd／PowerShell 執行時不算。"""
    if not tools.is_frozen() or sys.platform != "win32" or sys.stdin is None or not sys.stdin.isatty():
        return False
    import ctypes

    processes = (ctypes.c_uint32 * 2)()
    return bool(ctypes.windll.kernel32.GetConsoleProcessList(processes, 2) == 1)


def _wait_for_enter() -> None:
    try:
        input("\n按 Enter 關閉視窗…")
    except (EOFError, KeyboardInterrupt):
        pass


class _VersionAction(argparse.Action):
    """回報問題時要附的版本，一行一個。內建的 action="version" 會把換行排版成一行。"""

    def __call__(self, parser: argparse.ArgumentParser, namespace: argparse.Namespace, values: Any, option_string: str | None = None) -> None:
        print(f"critshowcase {_version('critshowcase')}")
        print(f"yt-dlp {_version('yt-dlp')}")
        parser.exit()


def _version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "（未安裝）"


def _default_output(source: Path) -> Path:
    return source.with_suffix(".mp4")
