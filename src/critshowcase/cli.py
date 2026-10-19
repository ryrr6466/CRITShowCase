"""命令列介面：critshowcase <zip 或 project.json>。"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from critshowcase.ffmpeg import RenderError, ToolMissing
from critshowcase.project import ProjectError, load_project
from critshowcase.render import render

EXIT_ERROR = 1


def main(argv: list[str] | None = None) -> int:
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
            render(project, output, workdir=Path(tmp))
    except (ProjectError, ToolMissing, RenderError) as error:
        print(f"critshowcase：{error}", file=sys.stderr)
        return EXIT_ERROR
    print(f"完成：{output}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="critshowcase",
        description="把 CRITShowCase（B50 影片）匯出的影片專案合成 mp4。",
    )
    parser.add_argument("input", help="網頁匯出的 zip，或解開後的 project.json")
    parser.add_argument("-o", "--output", help="輸出的 mp4 路徑（預設放在輸入檔旁邊）")
    return parser


def _default_output(source: Path) -> Path:
    return source.with_suffix(".mp4")
