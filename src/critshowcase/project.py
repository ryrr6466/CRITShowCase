"""影片專案（project.json 第 1 版）的讀取與驗證。

只讀出片工具需要的欄位（spec §8.2）：editor、group、song、score、comment 這些是給網頁還原編輯器用的，這裡不讀。
"""
from __future__ import annotations

import json
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

NOT_PROJECT = "這不是 CRITLOG 的影片專案。"
YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
TRANSITIONS = ("cut", "crossfade")


class ProjectError(Exception):
    """影片專案不能用；訊息直接顯示給使用者。"""


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class Clip:
    youtube_id: str
    start: float


@dataclass(frozen=True)
class Segment:
    kind: str
    frame: Path
    seconds: float
    video_box: Box | None = None
    clip: Clip | None = None


@dataclass(frozen=True)
class Output:
    width: int
    height: int
    transition: str
    transition_seconds: float


@dataclass(frozen=True)
class Project:
    output: Output
    segments: list[Segment]


def load_project(path: Path, workdir: Path | None = None) -> Project:
    """讀 project.json，或網頁匯出的 zip（解到 workdir，沒給就用暫存資料夾）。"""
    path = Path(path)
    if zipfile.is_zipfile(path):
        return _load_zip(path, Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="critshowcase-")))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProjectError(NOT_PROJECT) from error
    return _parse(data, path.parent)


def _load_zip(path: Path, workdir: Path) -> Project:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        if "project.json" not in names:
            raise ProjectError(f"{path.name} 裡沒有 project.json，請用 CRITShowCase 匯出的 zip。")
        try:
            data = json.loads(archive.read("project.json").decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProjectError(NOT_PROJECT) from error
        _check_header(data)
        # 只解出段落用到的畫面，名稱先驗證過，不會寫到 workdir 以外
        for segment in data.get("segments") or []:
            frame = segment.get("frame") if isinstance(segment, dict) else None
            if isinstance(frame, str) and _safe_relative(frame) and frame in names:
                archive.extract(frame, workdir)
    return _parse(data, workdir)


def _check_header(data) -> None:
    if not isinstance(data, dict) or data.get("createdWith") != "critlog.me":
        raise ProjectError(NOT_PROJECT)
    if data.get("schema") != 1:
        raise ProjectError(f"看不懂這個影片專案的版本（schema {data.get('schema')}），請更新 critshowcase。")


def _parse(data, base: Path) -> Project:
    _check_header(data)
    output = _output(data.get("output"))
    segments = data.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ProjectError(NOT_PROJECT)
    return Project(output=output, segments=[_segment(s, base) for s in segments])


def _output(value) -> Output:
    if not (
        isinstance(value, dict)
        and _positive_int(value.get("width"))
        and _positive_int(value.get("height"))
        and value.get("transition") in TRANSITIONS
        and _number(value.get("transitionSeconds"))
        and value["transitionSeconds"] >= 0
    ):
        raise ProjectError(NOT_PROJECT)
    return Output(value["width"], value["height"], value["transition"], float(value["transitionSeconds"]))


def _segment(value, base: Path) -> Segment:
    if not (
        isinstance(value, dict)
        and value.get("kind") in ("intro", "song", "outro")
        and isinstance(value.get("frame"), str)
        and _safe_relative(value["frame"])
        and _number(value.get("seconds"))
        and value["seconds"] > 0
    ):
        raise ProjectError(NOT_PROJECT)
    frame = base / value["frame"]
    if not frame.is_file():
        raise ProjectError(f"找不到畫面檔：{value['frame']}")
    if value["kind"] != "song":
        return Segment(value["kind"], frame, float(value["seconds"]))
    return Segment("song", frame, float(value["seconds"]), _box(value.get("videoBox")), _clip(value.get("clip", ...)))


def _box(value) -> Box:
    if not (isinstance(value, dict) and all(_int(value.get(k)) for k in "xy") and all(_positive_int(value.get(k)) for k in "wh")):
        raise ProjectError(NOT_PROJECT)
    return Box(value["x"], value["y"], value["w"], value["h"])


def _clip(value) -> Clip | None:
    if value is None:
        return None
    if not (
        isinstance(value, dict)
        and isinstance(value.get("youtubeId"), str)
        and YOUTUBE_ID.match(value["youtubeId"])
        and _number(value.get("start"))
        and value["start"] >= 0
    ):
        raise ProjectError(NOT_PROJECT)
    return Clip(value["youtubeId"], float(value["start"]))


def _safe_relative(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts and "\\" not in name and ":" not in name


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value and abs(value) != float("inf")


def _int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _positive_int(value) -> bool:
    return _int(value) and value > 0
