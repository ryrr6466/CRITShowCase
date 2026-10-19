"""測試共用的工具：產生畫面 PNG、組影片專案、用 ffprobe／ffmpeg 檢查輸出。"""
import json
import struct
import subprocess
import zipfile
import zlib
from pathlib import Path

import pytest

# 測試用小尺寸輸出，跑得快；影片框照 1920×1080 的比例縮小（40, 88, 1280, 720 → 約 1/6）
W, H = 320, 180
BOX = {"x": 8, "y": 16, "w": 192, "h": 108}


def write_png(path: Path, width: int, height: int, color, hole: dict | None = None) -> None:
    """純色 RGBA PNG；hole 範圍內是全透明（影片框）。"""
    r, g, b = color
    rows = []
    for y in range(height):
        row = bytearray([0])  # filter type 0
        for x in range(width):
            inside = hole and hole["x"] <= x < hole["x"] + hole["w"] and hole["y"] <= y < hole["y"] + hole["h"]
            row += bytes([0, 0, 0, 0]) if inside else bytes([r, g, b, 255])
        rows.append(bytes(row))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + chunk(b"IEND", b"")
    )


def intro(seconds=2, frame="frames/000-intro.png"):
    return {"kind": "intro", "frame": frame, "seconds": seconds, "title": "X-VERSE-X B50", "text": ""}


def song(n, seconds=3, clip=None):
    return {
        "kind": "song",
        "frame": f"frames/{n:03d}.png",
        "seconds": seconds,
        "videoBox": dict(BOX),
        "clip": clip,
        "group": "new",
        "groupRank": n,
        "overallRank": n,
        "song": {"id": 1000 + n, "title": "テスト", "difficulty": "master", "level": "14", "constant": 14.0},
        "score": {"value": 1007500, "rank": "sss", "rating": 16.0},
        "comment": "",
        "changed": False,
    }


def outro(seconds=2, frame="frames/051-outro.png"):
    return {"kind": "outro", "frame": frame, "seconds": seconds, "text": ""}


def project_dict(segments, transition="cut", **overrides):
    data = {
        "schema": 1,
        "game": "chunithm",
        "region": "international",
        "createdWith": "critlog.me",
        "notice": "非官方 · CRITLOG · 素材版權屬於 SEGA 及各權利人",
        "source": {"kind": "latest", "gameVersion": "CHUNITHM X-VERSE-X"},
        "editor": {"sortMode": "grouped", "direction": "countdown", "groupOrder": "newFirst", "clipSeconds": 10, "clipStart": 0},
        "output": {"width": W, "height": H, "transition": transition, "transitionSeconds": 0.5},
        "segments": segments,
    }
    data.update(overrides)
    return data


# 每個段落的畫面顏色，用來從輸出影片認出是哪一段
COLORS = [(220, 40, 40), (40, 200, 40), (40, 40, 220), (220, 200, 40), (200, 40, 200), (40, 200, 200)]


def write_project(folder: Path, data: dict, skip_frames=()) -> Path:
    """在 folder 寫出 project.json 與每個段落的畫面；歌曲段落的畫面挖出影片框。"""
    folder.mkdir(parents=True, exist_ok=True)
    for i, segment in enumerate(data["segments"]):
        if segment["frame"] in skip_frames:
            continue
        hole = segment.get("videoBox") if segment["kind"] == "song" else None
        write_png(folder / segment["frame"], data["output"]["width"], data["output"]["height"], COLORS[i % len(COLORS)], hole)
    path = folder / "project.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def write_zip(path: Path, folder: Path) -> Path:
    """仿網頁匯出的 store 格式 zip。"""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as z:
        for file in sorted(folder.rglob("*")):
            if file.is_file():
                z.write(file, file.relative_to(folder).as_posix())
    return path


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


def duration(path: Path) -> float:
    return float(probe(path)["format"]["duration"])


def pixel(path: Path, t: float, x: int, y: int) -> tuple[int, int, int]:
    """取 t 秒那一格在 (x, y) 的 RGB。"""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{t}", "-i", str(path), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        check=True, capture_output=True,
    ).stdout
    width = int(next(s for s in probe(path)["streams"] if s["codec_type"] == "video")["width"])
    i = (y * width + x) * 3
    return raw[i], raw[i + 1], raw[i + 2]


def close(actual, expected, tolerance=40) -> bool:
    return all(abs(a - e) <= tolerance for a, e in zip(actual, expected))


def mean_volume(path: Path, start: float, length: float) -> float:
    """[start, start+length] 的平均音量（dB）；完全靜音時回傳 -inf。"""
    err = subprocess.run(
        ["ffmpeg", "-v", "info", "-ss", f"{start}", "-t", f"{length}", "-i", str(path), "-af", "volumedetect", "-vn", "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    for line in err.splitlines():
        if "mean_volume:" in line:
            value = line.split("mean_volume:")[1].strip().split()[0]
            return float("-inf") if value == "-inf" else float(value)
    raise AssertionError(err)


class FakeDownloader:
    """不連網路：用 ffmpeg 產生純白畫面＋440Hz 聲音的片段，模擬 yt-dlp 下載好的那一段。"""

    def __init__(self, size=(160, 90), length=None, audio=True, fail=(), corrupt=()):
        self.size = size
        self.length = length  # None 表示剛好是要求的秒數
        self.audio = audio
        self.fail = set(fail)  # 這些影片 ID 下載失敗
        self.corrupt = set(corrupt)  # 這些影片 ID 下載到壞掉的檔案
        self.calls = []

    def fetch(self, clip, seconds, dest):
        from critshowcase.download import DownloadError

        self.calls.append((clip.youtube_id, clip.start, seconds))
        if clip.youtube_id in self.fail:
            raise DownloadError("影片設成私人")
        if clip.youtube_id in self.corrupt:
            path = Path(dest) / f"{clip.youtube_id}.mp4"
            path.write_bytes(b"not a video")
            return path
        length = self.length or seconds
        w, h = self.size
        path = Path(dest) / f"{clip.youtube_id}-{len(self.calls)}.mp4"
        args = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=white:s={w}x{h}:r=30:d={length}"]
        if self.audio:
            args += ["-f", "lavfi", "-i", f"sine=frequency=440:d={length}"]
        subprocess.run([*args, "-pix_fmt", "yuv420p", "-shortest", str(path)], check=True, capture_output=True)
        return path


CLIP = {"youtubeId": "dQw4w9WgXcQ", "start": 12.0}


@pytest.fixture
def make_project(tmp_path):
    """make_project(segments, ...) → project.json 的路徑。"""
    counter = iter(range(1000))

    def make(segments, transition="cut", skip_frames=(), **overrides):
        folder = tmp_path / f"project{next(counter)}"
        return write_project(folder, project_dict(segments, transition, **overrides), skip_frames)

    return make
