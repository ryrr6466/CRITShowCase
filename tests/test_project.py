"""seam：load_project(path) 讀取並驗證影片專案（spec §8）。"""
import json

import pytest

from conftest import intro, outro, song, write_zip
from critshowcase.project import ProjectError, load_project


def test_reads_segments_in_playback_order(make_project):
    path = make_project([intro(seconds=2), song(1, seconds=3), song(2, seconds=4), outro(seconds=5)])

    project = load_project(path)

    assert [s.kind for s in project.segments] == ["intro", "song", "song", "outro"]
    assert [s.seconds for s in project.segments] == [2, 3, 4, 5]
    assert all(s.frame.is_file() for s in project.segments)
    assert project.segments[1].frame.name == "001.png"


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"schema": 2}, "schema 2"),
        ({"createdWith": "elsewhere"}, "不是 CRITLOG 的影片專案"),
        ({"output": {"width": 320, "height": 180, "transition": "wipe", "transitionSeconds": 0.5}}, "不是 CRITLOG 的影片專案"),
    ],
)
def test_rejects_projects_it_cannot_play(make_project, overrides, message):
    path = make_project([song(1)], **overrides)

    with pytest.raises(ProjectError, match=message):
        load_project(path)


@pytest.mark.parametrize(
    "field, value",
    [("videoBox", None), ("clip", {"youtubeId": "not-an-id", "start": 0}), ("clip", {"youtubeId": "dQw4w9WgXcQ", "start": -1}), ("seconds", 0)],
)
def test_rejects_malformed_song_segment(make_project, field, value):
    bad = song(1)
    bad[field] = value
    path = make_project([bad])

    with pytest.raises(ProjectError, match="不是 CRITLOG 的影片專案"):
        load_project(path)


def test_rejects_file_that_is_not_json(tmp_path):
    path = tmp_path / "project.json"
    path.write_text("not json", encoding="utf-8")

    with pytest.raises(ProjectError, match="不是 CRITLOG 的影片專案"):
        load_project(path)


def test_rejects_missing_frame(make_project):
    path = make_project([song(1), song(2)], skip_frames={"frames/002.png"})

    with pytest.raises(ProjectError, match="frames/002.png"):
        load_project(path)


def test_rejects_frame_outside_project_folder(make_project):
    bad = song(1)
    bad["frame"] = "../outside.png"
    path = make_project([bad], skip_frames={"../outside.png"})
    (path.parent.parent / "outside.png").write_bytes(b"x")

    with pytest.raises(ProjectError, match="不是 CRITLOG 的影片專案"):
        load_project(path)


def test_reads_exported_zip(make_project, tmp_path):
    folder = make_project([intro(), song(1), outro()]).parent
    archive = write_zip(tmp_path / "critlog-chunithm-b50-video.zip", folder)

    project = load_project(archive, workdir=tmp_path / "work")

    assert [s.kind for s in project.segments] == ["intro", "song", "outro"]
    assert all(s.frame.is_file() for s in project.segments)


def test_rejects_zip_without_project_json(tmp_path):
    import zipfile

    archive = tmp_path / "other.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("readme.txt", "hi")

    with pytest.raises(ProjectError, match="project.json"):
        load_project(archive, workdir=tmp_path / "work")


def test_reads_song_clip_and_video_box(make_project):
    path = make_project([song(1, clip={"youtubeId": "dQw4w9WgXcQ", "start": 63.5}), song(2)])

    first, second = load_project(path).segments

    assert first.clip.youtube_id == "dQw4w9WgXcQ"
    assert first.clip.start == 63.5
    assert (first.video_box.x, first.video_box.y, first.video_box.w, first.video_box.h) == (8, 16, 192, 108)
    assert second.clip is None
