"""建出 Windows 免安裝版：dist/critshowcase-<版本>-windows-x64.zip。

用法：python packaging/build.py
需要：已安裝本專案與 PyInstaller（pip install -e ".[build]"）。

外部工具的下載網址與 sha256 固定寫在這裡，升級時手動改，建置結果才能重現。
zip 裡的 licenses 資料夾收齊所有隨附元件的授權文字。
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from dataclasses import dataclass, field
from importlib.metadata import distribution, packages_distributions, version
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
DIST = ROOT / "dist"
APP = DIST / "critshowcase"


@dataclass(frozen=True)
class Tool:
    url: str
    sha256: str
    # 壓縮檔裡要取出的檔案（比對路徑結尾）→ 放進 tools 資料夾的檔名
    files: dict[str, str]
    # 同上，放進 licenses 資料夾
    licenses: dict[str, str] = field(default_factory=dict)
    # 另外寫進 licenses 資料夾的說明：檔名 → 內容
    notices: dict[str, str] = field(default_factory=dict)


TOOLS = [
    # gyan.dev 的 essentials 建置：GPL，含輸出要用的 libx264
    Tool(
        url="https://github.com/GyanD/codexffmpeg/releases/download/9.0.2/ffmpeg-9.0.2-essentials_build.zip",
        sha256="60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba",
        files={"/bin/ffmpeg.exe": "ffmpeg.exe", "/bin/ffprobe.exe": "ffprobe.exe"},
        licenses={"/LICENSE": "ffmpeg-LICENSE.txt", "/README.txt": "ffmpeg-README.txt"},
        notices={
            "ffmpeg-SOURCE.txt": (
                "tools 資料夾裡的 ffmpeg.exe、ffprobe.exe 是 ffmpeg 9.0.2，以 GPL 授權（見 ffmpeg-LICENSE.txt）。\n"
                "這是 gyan.dev 的 essentials 建置：https://www.gyan.dev/ffmpeg/builds/\n"
                "\n"
                "原始碼：\n"
                "  ffmpeg 9.0.2：https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz\n"
                "  建置用到的各函式庫及其版本見 ffmpeg-README.txt，原始碼可從各專案取得。\n"
            ),
        },
    ),
    # yt-dlp 解 YouTube 驗證題用的 JS 執行環境
    Tool(
        url="https://github.com/denoland/deno/releases/download/v2.9.7/deno-x86_64-pc-windows-msvc.zip",
        sha256="a0c3101b4158d1dfb7d6a78a7bf0f3de80c96bb423c152beec8beb22786f2238",
        files={"deno.exe": "deno.exe"},
        # Deno 的 zip 裡沒有授權文字，放在 packaging/licenses
    ),
]


def main() -> None:
    if sys.platform != "win32":
        sys.exit("免安裝版只支援 Windows")
    archives = [download(tool) for tool in TOOLS]
    run_pyinstaller()
    tools_dir = APP / "tools"
    tools_dir.mkdir()
    for tool, archive in zip(TOOLS, archives):
        extract(archive, tool.files, tools_dir)
    write_licenses(APP / "licenses", archives)
    package = DIST / f"critshowcase-{version('critshowcase')}-windows-x64.zip"
    make_zip(APP, package)
    print(f"完成：{package}")
    print(f"zip {package.stat().st_size / 2**20:.0f} MB，解壓後 {folder_size(APP) / 2**20:.0f} MB")


def download(tool: Tool) -> Path:
    """下載到 build/downloads（已經有、而且 sha256 對就不重抓）。"""
    target = BUILD / "downloads" / tool.url.rsplit("/", 1)[-1]
    if not (target.is_file() and sha256(target) == tool.sha256):
        target.parent.mkdir(parents=True, exist_ok=True)
        print(f"下載 {tool.url}")
        partial = target.with_suffix(".part")
        with urllib.request.urlopen(tool.url) as response, partial.open("wb") as file:
            shutil.copyfileobj(response, file)
        actual = sha256(partial)
        if actual != tool.sha256:
            partial.unlink()
            sys.exit(f"{target.name} 的 sha256 不符：應為 {tool.sha256}，實際 {actual}")
        partial.replace(target)
    return target


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def run_pyinstaller() -> None:
    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--distpath", str(DIST), "--workpath", str(BUILD / "pyinstaller"),
            str(ROOT / "packaging" / "critshowcase.spec"),
        ],
        check=True,
    )


def extract(archive: Path, files: dict[str, str], dest: Path) -> None:
    with zipfile.ZipFile(archive) as z:
        for suffix, name in files.items():
            member = next((m for m in z.namelist() if m.endswith(suffix)), None)
            if member is None:
                sys.exit(f"{archive.name} 裡找不到 {suffix}")
            with z.open(member) as source, (dest / name).open("wb") as target:
                shutil.copyfileobj(source, target)


def write_licenses(dest: Path, archives: list[Path]) -> None:
    dest.mkdir()
    shutil.copyfile(ROOT / "LICENSE", dest / "critshowcase-LICENSE.txt")
    for file in (ROOT / "packaging" / "licenses").iterdir():
        shutil.copyfile(file, dest / file.name)
    for tool, archive in zip(TOOLS, archives):
        extract(archive, tool.licenses, dest)
        for name, text in tool.notices.items():
            (dest / name).write_text(text, encoding="utf-8")
    # PyInstaller 隨附的 Python 執行環境；Windows 版的 LICENSE.txt 也列了 OpenSSL、libffi、SQLite 等
    shutil.copyfile(Path(sys.base_prefix) / "LICENSE.txt", dest / "python-LICENSE.txt")
    packages = dest / "python-packages"
    for name in bundled_distributions():
        dist = distribution(name)
        folder = packages / f"{dist.metadata['Name']}-{dist.version}"
        folder.mkdir(parents=True)
        # 只看套件自己的 .dist-info；套件內附的其他套件（例如 setuptools/_vendor）授權檔同名會互相蓋掉
        files = [
            f for f in dist.files or []
            if f.parts[0].endswith(".dist-info") and any(k in f.name.upper() for k in ("LICEN", "COPYING", "NOTICE"))
        ]
        for file in files:
            shutil.copyfile(Path(str(file.locate())), folder / file.name)
        if not files:
            summary = dist.metadata.get("License-Expression") or dist.metadata.get("License") or "（套件沒有附授權資訊）"
            (folder / "LICENSE.txt").write_text(summary, encoding="utf-8")


def bundled_distributions() -> list[str]:
    """實際包進 exe 的第三方套件：照 PyInstaller 收進去的模組對回套件，不用猜。"""
    from PyInstaller.archive.readers import ZlibArchiveReader

    modules = {name.split(".")[0] for name in ZlibArchiveReader(str(BUILD / "pyinstaller" / "critshowcase" / "PYZ-00.pyz")).toc}
    modules |= {path.name.split(".")[0] for path in (APP / "_internal").iterdir()}
    owners = packages_distributions()
    return sorted({dist for module in modules for dist in owners.get(module, [])} - {"critshowcase"})


def make_zip(folder: Path, package: Path) -> None:
    """zip 裡最上層是 critshowcase 資料夾，解壓後不會散成一地。"""
    package.unlink(missing_ok=True)
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for file in sorted(folder.rglob("*")):
            if file.is_file():
                z.write(file, (folder.name / file.relative_to(folder)).as_posix())


def folder_size(folder: Path) -> int:
    return sum(file.stat().st_size for file in folder.rglob("*") if file.is_file())


if __name__ == "__main__":
    main()
