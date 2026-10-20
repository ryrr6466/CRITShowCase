"""命令列介面：critshowcase <zip 或 project.json>。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from critshowcase import package_version, tools
from critshowcase.cache import default_cache_dir
from critshowcase.download import Downloader
from critshowcase.job import EXIT_ERROR, run_job
from critshowcase.render import Progress

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
    result = run_job(
        Path(args.input),
        Path(args.output) if args.output else None,
        cookies_from_browser=args.cookies_from_browser,
        cookies=Path(args.cookies) if args.cookies else None,
        refresh=args.refresh,
        verbose=args.verbose,
        downloader=downloader,
        progress=_print_progress,
    )
    if result.error is not None:
        print(f"critshowcase：{result.error}", file=sys.stderr)
        return result.exit_code
    print(f"完成：{result.output}")
    if result.failures:
        print(f"\n有 {len(result.failures)} 個片段下載失敗，這些段落改成靜態畫面：", file=sys.stderr)
        for failure in result.failures:
            print(f"  第 {failure.position} 段  {failure.youtube_id}  {failure.reason}", file=sys.stderr)
        print("可以回 CRITShowCase 頁面換掉這些片段，重新匯出後再執行一次。", file=sys.stderr)
        if result.update_hint:
            print(result.update_hint, file=sys.stderr)
    return result.exit_code


def _print_progress(event: Progress) -> None:
    # 完成的訊息等結果出來再印
    if event.stage != "done":
        print(event.message, flush=True)


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
        print(f"critshowcase {package_version('critshowcase')}")
        print(f"yt-dlp {package_version('yt-dlp')}")
        parser.exit()
