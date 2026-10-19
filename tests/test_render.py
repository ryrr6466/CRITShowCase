"""seam：render(project, output, downloader=…) 從頭到尾的合成，用 ffprobe 與抽樣像素檢查成品（spec §8.3）。"""
import pytest

from conftest import BOX, COLORS, H, W, close, duration, intro, mean_volume, outro, pixel, probe, song
from critshowcase.project import load_project
from critshowcase.render import render


def streams(path, kind):
    return [s for s in probe(path)["streams"] if s["codec_type"] == kind]


def test_static_project_becomes_mp4_of_frames_in_order(make_project, tmp_path):
    project = load_project(make_project([intro(seconds=2), song(1, seconds=3), song(2, seconds=3), outro(seconds=2)]))
    out = tmp_path / "out.mp4"

    render(project, out)

    video = streams(out, "video")[0]
    assert (video["width"], video["height"]) == (W, H)
    assert duration(out) == pytest.approx(10, abs=0.15)
    # 每段的畫面照順序出現（取每段中間的一格，畫面上影片框以外的地方）
    for t, color in [(1, COLORS[0]), (3.5, COLORS[1]), (6.5, COLORS[2]), (9, COLORS[3])]:
        assert close(pixel(out, t, W - 10, H - 10), color), t
    # 沒有片段的影片框露出黑底
    assert close(pixel(out, 3.5, BOX["x"] + BOX["w"] // 2, BOX["y"] + BOX["h"] // 2), (0, 0, 0))
    # 有音軌，而且是靜音
    assert streams(out, "audio")
    assert mean_volume(out, 0, 10) < -80
