"""seam：render(project, output, downloader=…) 從頭到尾的合成，用 ffprobe 與抽樣像素檢查成品（spec §8.3）。"""
import pytest

from conftest import BOX, CLIP, COLORS, H, W, FakeDownloader, close, duration, intro, mean_volume, outro, pixel, probe, song
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


BOX_CENTER = (BOX["x"] + BOX["w"] // 2, BOX["y"] + BOX["h"] // 2)
WHITE, BLACK = (255, 255, 255), (0, 0, 0)


def test_clip_plays_inside_video_box_under_frame(make_project, tmp_path):
    project = load_project(make_project([intro(seconds=2), song(1, seconds=3, clip=CLIP), outro(seconds=2)]))
    downloader = FakeDownloader(size=(160, 90))
    out = tmp_path / "out.mp4"

    render(project, out, downloader=downloader)

    # 只要求需要的那一段
    assert downloader.calls == [("dQw4w9WgXcQ", 12.0, 3)]
    assert duration(out) == pytest.approx(7, abs=0.15)
    # 16:9 片段剛好填滿影片框；框外仍是畫面
    assert close(pixel(out, 3.5, *BOX_CENTER), WHITE)
    assert close(pixel(out, 3.5, BOX["x"] + 2, BOX["y"] + 2), WHITE)
    assert close(pixel(out, 3.5, BOX["x"] - 3, BOX_CENTER[1]), COLORS[1])
    assert close(pixel(out, 3.5, W - 10, H - 10), COLORS[1])
    # 歌曲段落有片段的聲音，開頭與結尾靜音
    assert mean_volume(out, 2.3, 2.4) > -40
    assert mean_volume(out, 0, 1.8) < -80
    assert mean_volume(out, 5.2, 1.6) < -80


@pytest.mark.parametrize(
    "size, bar_point",
    [
        ((160, 120), (BOX["x"] + 5, BOX_CENTER[1])),  # 4:3 → 左右補黑邊
        ((90, 160), (BOX["x"] + 40, BOX_CENTER[1])),  # 直式（Shorts）→ 左右補更寬的黑邊
        ((240, 60), (BOX_CENTER[0], BOX["y"] + 5)),  # 4:1 → 上下補黑邊
    ],
)
def test_clip_keeps_aspect_ratio_with_black_bars(make_project, tmp_path, size, bar_point):
    project = load_project(make_project([song(1, seconds=3, clip=CLIP)]))
    out = tmp_path / "out.mp4"

    render(project, out, downloader=FakeDownloader(size=size))

    assert close(pixel(out, 1.5, *BOX_CENTER), WHITE)
    assert close(pixel(out, 1.5, *bar_point), BLACK)


def test_short_clip_still_fills_segment_seconds(make_project, tmp_path):
    project = load_project(make_project([song(1, seconds=4, clip=CLIP), song(2, seconds=3)]))
    out = tmp_path / "out.mp4"

    render(project, out, downloader=FakeDownloader(length=1.5))

    assert duration(out) == pytest.approx(7, abs=0.15)
    # 片段放完後停在最後一格，下一段照時間開始
    assert close(pixel(out, 3, *BOX_CENTER), WHITE)
    assert close(pixel(out, 5.5, W - 10, H - 10), COLORS[1])


def test_long_clip_is_cut_to_segment_seconds(make_project, tmp_path):
    project = load_project(make_project([song(1, seconds=3, clip=CLIP), song(2, seconds=3)]))
    out = tmp_path / "out.mp4"

    render(project, out, downloader=FakeDownloader(length=8))

    assert duration(out) == pytest.approx(6, abs=0.15)
    assert mean_volume(out, 3.3, 2.4) < -80


def test_clip_without_audio_is_silent(make_project, tmp_path):
    project = load_project(make_project([song(1, seconds=3, clip=CLIP)]))
    out = tmp_path / "out.mp4"

    render(project, out, downloader=FakeDownloader(audio=False))

    assert duration(out) == pytest.approx(3, abs=0.15)
    assert mean_volume(out, 0, 3) < -80


def test_missing_yt_dlp_is_reported(make_project, tmp_path, monkeypatch):
    import sys

    from critshowcase.ffmpeg import ToolMissing

    monkeypatch.setitem(sys.modules, "yt_dlp", None)
    project = load_project(make_project([song(1, seconds=3, clip=CLIP)]))

    with pytest.raises(ToolMissing, match="yt-dlp"):
        render(project, tmp_path / "out.mp4")


GOOD = {"youtubeId": "aaaaaaaaaaa", "start": 0}
GONE = {"youtubeId": "bbbbbbbbbbb", "start": 0}
BROKEN = {"youtubeId": "ccccccccccc", "start": 0}


def test_failed_download_becomes_static_segment_and_is_reported(make_project, tmp_path):
    project = load_project(make_project([intro(seconds=2), song(1, seconds=3, clip=GOOD), song(2, seconds=3, clip=GONE), outro(seconds=2)]))
    out = tmp_path / "out.mp4"

    report = render(project, out, downloader=FakeDownloader(fail={GONE["youtubeId"]}))

    assert duration(out) == pytest.approx(10, abs=0.15)
    # 下載成功的照常播放，失敗的那段是靜態畫面＋靜音
    assert close(pixel(out, 3.5, *BOX_CENTER), WHITE)
    assert close(pixel(out, 6.5, *BOX_CENTER), BLACK)
    assert close(pixel(out, 6.5, W - 10, H - 10), COLORS[2])
    assert mean_volume(out, 5.3, 2.4) < -80
    assert [(f.position, f.youtube_id, f.reason) for f in report.failures] == [(3, "bbbbbbbbbbb", "影片設成私人")]


def test_every_download_failing_still_outputs_whole_video(make_project, tmp_path):
    project = load_project(make_project([song(1, seconds=3, clip=GONE), song(2, seconds=3, clip=GONE)]))
    out = tmp_path / "out.mp4"

    report = render(project, out, downloader=FakeDownloader(fail={GONE["youtubeId"]}))

    assert duration(out) == pytest.approx(6, abs=0.15)
    assert [f.position for f in report.failures] == [1, 2]


def test_unreadable_clip_is_treated_as_failed_download(make_project, tmp_path):
    project = load_project(make_project([song(1, seconds=3, clip=BROKEN)]))
    out = tmp_path / "out.mp4"

    report = render(project, out, downloader=FakeDownloader(corrupt={BROKEN["youtubeId"]}))

    assert duration(out) == pytest.approx(3, abs=0.15)
    assert [f.youtube_id for f in report.failures] == ["ccccccccccc"]


def test_successful_render_reports_no_failures(make_project, tmp_path):
    project = load_project(make_project([song(1, seconds=3, clip=GOOD)]))

    report = render(project, tmp_path / "out.mp4", downloader=FakeDownloader())

    assert report.failures == []
