"""建出免安裝版：Windows 是 dist/critshowcase-<版本>-windows-x64.zip，
Apple Silicon 的 macOS 是 dist/critshowcase-<版本>-macos-arm64.zip（裡面是簽章、公證過的 CRITShowCase.app）。

用法：python packaging/build.py（在哪個平台執行就建哪個平台的版本）
需要：已安裝本專案與 PyInstaller（pip install -e ".[build]"）；macOS 的簽章設定見 build_macos()。

外部工具的下載網址與 sha256 固定寫在這裡，升級時手動改，建置結果才能重現。
zip 裡的 licenses 資料夾收齊所有隨附元件的授權文字。
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
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


WINDOWS_TOOLS = [
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

# martin-riedl.de 的 ffmpeg 有 macOS Apple Silicon 的 release 建置；zip 裡只有執行檔，GPLv3 全文放在 packaging/licenses/macos
FFMPEG_MACOS = "https://ffmpeg.martin-riedl.de/download/macos/arm64/1789931890_9.0.2"
MACOS_TOOLS = [
    Tool(
        url=f"{FFMPEG_MACOS}/ffmpeg.zip",
        sha256="c8ed4c4e6978a03c485edbfe4e0a5dc2380f8a30bba5150531b31b094492d924",
        files={"ffmpeg": "ffmpeg"},
        notices={
            "ffmpeg-SOURCE.txt": (
                "CRITShowCase.app/Contents/MacOS/tools 裡的 ffmpeg、ffprobe 是 ffmpeg 9.0.2，以 GPLv3 授權（見 ffmpeg-LICENSE.txt）。\n"
                "這是 martin-riedl.de 的 macOS Apple Silicon release 建置：https://ffmpeg.martin-riedl.de/\n"
                "\n"
                "原始碼：\n"
                "  ffmpeg 9.0.2：https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz\n"
                f"  建置設定與各函式庫的版本：{FFMPEG_MACOS}/versions.txt\n"
                "  建置腳本：https://git.martin-riedl.de/ffmpeg/build-script\n"
            ),
        },
    ),
    Tool(
        url=f"{FFMPEG_MACOS}/ffprobe.zip",
        sha256="fcbe839537485eaee7a7a8bc5cbc0f90d53617e80943e8a5b2e31cb851197ea6",
        files={"ffprobe": "ffprobe"},
    ),
    Tool(
        url="https://github.com/denoland/deno/releases/download/v2.9.7/deno-aarch64-apple-darwin.zip",
        sha256="5cd46d6268f6f78f5d88bdc7159d20bd44cdaa4b3303474839f87ec6fe7ae25c",
        files={"deno": "deno"},
    ),
]

MACOS = ROOT / "packaging" / "macos"
APP_BUNDLE = DIST / "CRITShowCase.app"
# 放進 zip 的資料夾：CRITShowCase.app 與 licenses
MACOS_STAGE = DIST / "CRITShowCase"


def main() -> None:
    if sys.platform == "win32":
        build_windows()
    elif sys.platform == "darwin" and platform.machine() == "arm64":
        build_macos()
    else:
        sys.exit("免安裝版只支援 Windows x64 與 Apple Silicon 的 macOS")


def build_windows() -> None:
    archives = [download(tool) for tool in WINDOWS_TOOLS]
    run_pyinstaller()
    tools_dir = APP / "tools"
    tools_dir.mkdir()
    for tool, archive in zip(WINDOWS_TOOLS, archives):
        extract(archive, tool.files, tools_dir)
    write_licenses(APP / "licenses", WINDOWS_TOOLS, archives)
    package = DIST / f"critshowcase-{version('critshowcase')}-windows-x64.zip"
    make_zip(APP, package)
    print(f"完成：{package}")
    print(f"zip {package.stat().st_size / 2**20:.0f} MB，解壓後 {folder_size(APP) / 2**20:.0f} MB")


def build_macos() -> None:
    """簽章與公證的設定從環境變數讀（見 README「建置 macOS 版」）；沒設 MACOS_SIGN_IDENTITY 時只做 ad-hoc 簽章，只能在本機測試。"""
    identity = os.environ.get("MACOS_SIGN_IDENTITY") or None
    if identity is None and os.environ.get("SIGN_REQUIRED"):
        sys.exit("要發布的 macOS 版一定要簽章：請設定 MACOS_SIGN_IDENTITY")
    notary = notary_credentials() if identity else None
    archives = [download(tool) for tool in MACOS_TOOLS]
    run_pyinstaller()
    tools_dir = APP_BUNDLE / "Contents" / "MacOS" / "tools"
    tools_dir.mkdir()
    for tool, archive in zip(MACOS_TOOLS, archives):
        extract(archive, tool.files, tools_dir)
    for file in tools_dir.iterdir():
        file.chmod(0o755)
    sign_app(APP_BUNDLE, identity or "-")
    if notary:
        notarize(APP_BUNDLE, notary)
    else:
        print("沒有設定簽章：只做了 ad-hoc 簽章、沒有公證，從網路下載的人打不開，只能自己測試用")
    shutil.rmtree(MACOS_STAGE, ignore_errors=True)
    MACOS_STAGE.mkdir()
    shutil.move(APP_BUNDLE, MACOS_STAGE / APP_BUNDLE.name)
    write_licenses(MACOS_STAGE / "licenses", MACOS_TOOLS, archives)
    package = DIST / f"critshowcase-{version('critshowcase')}-macos-arm64.zip"
    package.unlink(missing_ok=True)
    # ditto 保留 app 裡的符號連結、權限與簽章；Python 的 zipfile 會弄壞
    subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(MACOS_STAGE), str(package)], check=True)
    print(f"完成：{package}")
    print(f"zip {package.stat().st_size / 2**20:.0f} MB，解壓後 {folder_size(MACOS_STAGE) / 2**20:.0f} MB")


def notary_credentials() -> list[str]:
    """notarytool 的登入方式：本機用 store-credentials 存好的 profile；CI 用 App Store Connect API key。"""
    if os.environ.get("NOTARY_PROFILE"):
        return ["--keychain-profile", os.environ["NOTARY_PROFILE"]]
    key = {name: os.environ.get(name) for name in ("NOTARY_KEY", "NOTARY_KEY_ID", "NOTARY_ISSUER")}
    if not all(key.values()):
        sys.exit("有簽章就要公證：請設定 NOTARY_PROFILE，或 NOTARY_KEY、NOTARY_KEY_ID、NOTARY_ISSUER")
    return ["--key", str(key["NOTARY_KEY"]), "--key-id", str(key["NOTARY_KEY_ID"]), "--issuer", str(key["NOTARY_ISSUER"])]


def sign_app(app: Path, identity: str) -> None:
    """由內而外簽：動態函式庫、framework、tools、命令列版，最後是整個 app（也就簽了 GUI 主程式）。

    開 hardened runtime（公證的條件）；Python 與 Deno 需要的例外寫在 packaging/macos 的 entitlements。
    """
    entitlements = MACOS / "entitlements.plist"
    executables = app / "Contents" / "MacOS"
    main_program = executables / plistlib.loads((app / "Contents" / "Info.plist").read_bytes())["CFBundleExecutable"]
    # 深的先簽：外層的簽章會記錄裡面檔案的雜湊
    files = sorted((f for f in app.rglob("*") if is_macho(f) and f != main_program), key=lambda f: len(f.parts), reverse=True)
    for file in files:
        if file.parent == executables / "tools":
            codesign(file, identity, MACOS / "entitlements-deno.plist" if file.name == "deno" else None)
        elif file.parent == executables:
            codesign(file, identity, entitlements)
        else:
            codesign(file, identity, None)
    for framework in sorted(app.rglob("*.framework"), key=lambda f: len(f.parts), reverse=True):
        if framework.is_dir() and not framework.is_symlink():
            codesign(framework, identity, None)
    codesign(app, identity, entitlements)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)], check=True)


def is_macho(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    with path.open("rb") as file:
        return file.read(4) in MACHO_MAGIC


# 64 位元 Mach-O（兩種位元組順序）與 universal binary
MACHO_MAGIC = {b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}


def codesign(path: Path, identity: str, entitlements: Path | None) -> None:
    command = ["codesign", "--force", "--options", "runtime", "--sign", identity]
    if identity != "-":
        # 公證要求 Apple 的時間戳；ad-hoc 簽章沒有
        command.append("--timestamp")
    if entitlements:
        command += ["--entitlements", str(entitlements)]
    subprocess.run([*command, str(path)], check=True, stdout=subprocess.DEVNULL)


def notarize(app: Path, credentials: list[str]) -> None:
    """送 Apple 公證、等結果，通過後把公證票釘在 app 上：沒有網路的電腦第一次打開也不會被擋。"""
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "notarize.zip"
        subprocess.run(["ditto", "-c", "-k", "--keepParent", str(app), str(archive)], check=True)
        print("送出公證，通常要幾分鐘…", flush=True)
        result = subprocess.run(
            ["xcrun", "notarytool", "submit", str(archive), *credentials, "--wait", "--output-format", "json"],
            capture_output=True, text=True,
        )
    submission = json.loads(result.stdout or "{}")
    if submission.get("status") != "Accepted":
        if submission.get("id"):
            subprocess.run(["xcrun", "notarytool", "log", submission["id"], *credentials])
        sys.exit(f"公證沒有通過：{submission.get('status') or result.stderr.strip()}")
    subprocess.run(["xcrun", "stapler", "staple", str(app)], check=True)
    subprocess.run(["spctl", "--assess", "--type", "execute", "--verbose=2", str(app)], check=True)


def download(tool: Tool) -> Path:
    """下載到 build/downloads（已經有、而且 sha256 對就不重抓）。"""
    target = BUILD / "downloads" / tool.url.rsplit("/", 1)[-1]
    if not (target.is_file() and sha256(target) == tool.sha256):
        target.parent.mkdir(parents=True, exist_ok=True)
        print(f"下載 {tool.url}")
        partial = target.with_suffix(".part")
        fetch(tool.url, partial)
        actual = sha256(partial)
        if actual != tool.sha256:
            partial.unlink()
            sys.exit(f"{target.name} 的 sha256 不符：應為 {tool.sha256}，實際 {actual}")
        partial.replace(target)
    return target


def fetch(url: str, dest: Path, attempts: int = 4) -> None:
    """下載中斷時重試幾次：martin-riedl.de 是個人架的伺服器，偶爾會斷線（Connection reset by peer）。"""
    # martin-riedl.de 擋 urllib 預設的 User-Agent（403）
    request = urllib.request.Request(url, headers={"User-Agent": "critshowcase-build"})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response, dest.open("wb") as file:
                shutil.copyfileobj(response, file)
            return
        except (OSError, urllib.error.URLError) as error:
            if attempt == attempts:
                raise
            print(f"下載失敗（{error}），{attempt * 10} 秒後重試", flush=True)
            time.sleep(attempt * 10)


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


def write_licenses(dest: Path, tools: list[Tool], archives: list[Path]) -> None:
    """packaging/licenses 最上層的檔案每個平台都放；macos 子資料夾只有 macOS 版放。"""
    dest.mkdir()
    shutil.copyfile(ROOT / "LICENSE", dest / "critshowcase-LICENSE.txt")
    licenses = ROOT / "packaging" / "licenses"
    extra = [licenses / "macos"] if sys.platform == "darwin" else []
    for folder in (licenses, *extra):
        for file in folder.iterdir():
            if file.is_file():
                shutil.copyfile(file, dest / file.name)
    for tool, archive in zip(tools, archives):
        extract(archive, tool.licenses, dest)
        for name, text in tool.notices.items():
            (dest / name).write_text(text, encoding="utf-8")
    # PyInstaller 隨附的 Python 執行環境；Windows 版的 LICENSE.txt 也列了 OpenSSL、libffi、SQLite 等
    base = Path(sys.base_prefix)
    python_license = next(
        (p for p in (base / "LICENSE.txt", base / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "LICENSE.txt") if p.is_file()),
        None,
    )
    if python_license is None:
        sys.exit(f"找不到 Python 的 LICENSE.txt（{base}）")
    shutil.copyfile(python_license, dest / "python-LICENSE.txt")
    write_tcl_tk_licenses(dest)
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


def write_tcl_tk_licenses(dest: Path) -> None:
    """GUI 用的 Tcl／Tk 要保留著作權聲明，Python 的 LICENSE.txt 沒有列。

    Windows 的 Python 3.14 起 Tcl／Tk 的 library 包成 tcl\\libtcl*.zip、libtk*.zip，更早的版本是資料夾；
    macOS 的在 lib 底下，Tcl 9 的 library 是接在 libtcl9.0.dylib 後面的 zip（zipfs）。
    都找不到時，用 PyInstaller 收進去的那份。
    """
    base = Path(sys.base_prefix)
    for name in ("tcl", "tk"):
        text = None
        for tcl in (base / "tcl", base / "lib"):
            archives = [*tcl.glob(f"lib{name}*.zip"), *tcl.glob(f"lib{name}*.dylib")]
            for archive in (a for a in archives if zipfile.is_zipfile(a)):
                with zipfile.ZipFile(archive) as z:
                    member = next((m for m in z.namelist() if m.endswith("license.terms")), None)
                    if member:
                        text = z.read(member)
            for folder in tcl.glob(f"{name}[0-9]*"):
                if (folder / "license.terms").is_file():
                    text = (folder / "license.terms").read_bytes()
        bundled = APP / "_internal" / f"_{name}_data" / "license.terms"
        if text is None and bundled.is_file():
            text = bundled.read_bytes()
        if text is None:
            candidates = [str(p) for p in (base / "lib").glob(f"*{name}*")] + [str(p) for p in (base / "tcl").glob("*")]
            sys.exit(f"找不到 {name} 的 license.terms（{base}）；找過：{candidates}")
        (dest / f"{name}-license.terms.txt").write_bytes(text)


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
