"""對建好的免安裝版做煙霧測試，在 PATH 上沒有 ffmpeg、Python、Deno、Node 的環境執行 exe。

用法：python packaging/smoke.py dist/critshowcase [--youtube]
--youtube 會真的從 YouTube 下載一個片段；網路或 YouTube 可能讓它失敗，所以預設不跑。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SMOKE = Path(__file__).resolve().parent / "smoke"
MISSING = ("ffmpeg", "ffprobe", "python", "deno", "node")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("app", type=Path, help="解壓後的 critshowcase 資料夾")
    parser.add_argument("--youtube", action="store_true", help="也測試實際下載 YouTube 片段")
    args = parser.parse_args()
    exe = args.app / "critshowcase.exe"
    env = clean_env()

    run(exe, ["--version"], env)
    run(exe, ["--help"], env)
    with tempfile.TemporaryDirectory() as tmp:
        check_render(exe, args.app, SMOKE / "static.zip", Path(tmp) / "static.mp4", 7, env)
        if args.youtube:
            check_render(exe, args.app, SMOKE / "youtube.zip", Path(tmp) / "youtube.mp4", 4, env)
    print("煙霧測試通過")


def clean_env() -> dict[str, str]:
    """PATH 只留 Windows 系統資料夾，確認 exe 不靠使用者裝的工具。"""
    root = os.environ.get("SYSTEMROOT", r"C:\Windows")
    path = os.pathsep.join([str(Path(root) / "System32"), root])
    for name in MISSING:
        found = shutil.which(name, path=path)
        if found:
            sys.exit(f"測試環境的 PATH 上不該有 {name}：{found}")
    return {**os.environ, "PATH": path}


def run(exe: Path, args: list[str], env: dict[str, str], expect: int = 0) -> None:
    print(f"$ critshowcase {' '.join(args)}", flush=True)
    # stdin 接 DEVNULL：不會停下來等使用者按鍵
    result = subprocess.run([str(exe), *args], env=env, stdin=subprocess.DEVNULL)
    if result.returncode != expect:
        sys.exit(f"結束碼 {result.returncode}，應為 {expect}")


def check_render(exe: Path, app: Path, project: Path, output: Path, seconds: float, env: dict[str, str]) -> None:
    # --refresh：不用片段快取，每次都真的下載
    run(exe, [str(project), "-o", str(output), "--refresh"], env)
    probe = subprocess.run(
        [str(app / "tools" / "ffprobe.exe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(output)],
        check=True, capture_output=True, text=True,
    )
    actual = float(probe.stdout)
    if abs(actual - seconds) > 0.15:
        sys.exit(f"{output.name} 長度 {actual} 秒，應為 {seconds} 秒")


if __name__ == "__main__":
    main()
