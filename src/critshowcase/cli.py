"""命令列介面：critshowcase <zip 或 project.json>。"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from critshowcase.cache import CachedDownloader, default_cache_dir
from critshowcase.download import DownloadBlocked, Downloader, YtDlpDownloader
from critshowcase.ffmpeg import RenderError, ToolMissing
from critshowcase.project import ProjectError, load_project
from critshowcase.render import render

EXIT_ERROR = 1
# 影片輸出了，但有片段下載失敗、改成靜態畫面
EXIT_PARTIAL = 3


def main(argv: list[str] | None = None, downloader: Downloader | None = None) -> int:
    """downloader 給測試注入；沒給時影片專案有片段才建立 yt-dlp 下載器。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
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
                    YtDlpDownloader(args.cookies_from_browser, Path(args.cookies) if args.cookies else None, workdir=Path(tmp)),
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
        return EXIT_PARTIAL
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="critshowcase",
        description="把 CRITShowCase（B50 影片）匯出的影片專案合成 mp4。",
    )
    parser.add_argument("input", help="網頁匯出的 zip，或解開後的 project.json")
    parser.add_argument("-o", "--output", help="輸出的 mp4 路徑（預設放在輸入檔旁邊）")
    parser.add_argument("--cookies-from-browser", metavar="BROWSER", help="YouTube 要求登入驗證時，使用這個瀏覽器的 cookies（例如 firefox、chrome）")
    parser.add_argument("--cookies", metavar="FILE", help="YouTube 要求登入驗證時，使用匯出的 cookies.txt")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help=f"不用快取，所有片段重新下載（快取在 {default_cache_dir()}，可以直接刪除）",
    )
    return parser


def _default_output(source: Path) -> Path:
    return source.with_suffix(".mp4")
