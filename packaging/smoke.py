"""對建好的免安裝版做煙霧測試，在 PATH 上沒有 ffmpeg、Python、Deno、Node 的環境執行 exe。

用法：python packaging/smoke.py dist/critshowcase [--youtube]（macOS：dist/CRITShowCase）
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
    parser.add_argument("app", type=Path, help="解壓後的資料夾：Windows 是 critshowcase，macOS 是放著 CRITShowCase.app 的 CRITShowCase")
    parser.add_argument("--youtube", action="store_true", help="也測試實際下載 YouTube 片段")
    args = parser.parse_args()
    exe, gui, tools = layout(args.app)
    env = clean_env()

    run(exe, ["--version"], env)
    run(exe, ["--help"], env)
    check_gui(gui, env)
    with tempfile.TemporaryDirectory() as tmp:
        check_render(exe, tools, SMOKE / "static.zip", Path(tmp) / "static.mp4", 7, env)
        if args.youtube:
            check_render(exe, tools, SMOKE / "youtube.zip", Path(tmp) / "youtube.mp4", 4, env)
    print("煙霧測試通過")


def layout(app: Path) -> tuple[Path, Path, Path]:
    """（命令列版、GUI、tools 資料夾）。"""
    if sys.platform == "darwin":
        executables = app / "CRITShowCase.app" / "Contents" / "MacOS"
        return executables / "critshowcase", executables / "critshowcase-gui", executables / "tools"
    return app / "critshowcase.exe", app / "critshowcase-gui.exe", app / "tools"


def clean_env() -> dict[str, str]:
    """PATH 只留系統資料夾，確認 exe 不靠使用者裝的工具。"""
    if sys.platform == "darwin":
        path = os.pathsep.join(["/usr/bin", "/bin", "/usr/sbin", "/sbin"])
    else:
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


def check_gui(exe: Path, env: dict[str, str]) -> None:
    """GUI 沒有 console：設了 CRITSHOWCASE_GUI_SMOKE 時視窗開起來一秒就自己關掉。

    exe 出錯時 PyInstaller 會跳出對話框一直停著，所以用逾時判斷，不能只等它結束。
    """
    print("$ critshowcase-gui（開視窗後自動關閉）", flush=True)
    try:
        result = subprocess.run([str(exe)], env={**env, "CRITSHOWCASE_GUI_SMOKE": "1"}, timeout=60)
    except subprocess.TimeoutExpired:
        sys.exit("critshowcase-gui 60 秒內沒有自己關閉（可能跳出了錯誤對話框）")
    if result.returncode != 0:
        sys.exit(f"critshowcase-gui 結束碼 {result.returncode}，應為 0")


def check_render(exe: Path, tools: Path, project: Path, output: Path, seconds: float, env: dict[str, str]) -> None:
    # --refresh：不用片段快取，每次都真的下載
    run(exe, [str(project), "-o", str(output), "--refresh"], env)
    probe = subprocess.run(
        [str(tools / ("ffprobe.exe" if sys.platform == "win32" else "ffprobe")), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(output)],
        check=True, capture_output=True, text=True,
    )
    actual = float(probe.stdout)
    if abs(actual - seconds) > 0.15:
        sys.exit(f"{output.name} 長度 {actual} 秒，應為 {seconds} 秒")


if __name__ == "__main__":
    main()
