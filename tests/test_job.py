"""seam：出片工作 run_job 的結果與進度事件（CLI 與 GUI 共用）。"""
import pytest

from conftest import FakeDownloader, duration, intro, outro, song
from critshowcase.job import run_job


def test_completed_job_reports_output(make_project, tmp_path):
    path = make_project([intro(seconds=2), song(1, seconds=3)])
    out = tmp_path / "out.mp4"

    result = run_job(path, out)

    assert result.exit_code == 0
    assert result.output == out
    assert result.failures == []
    assert result.error is None
    assert duration(out) == pytest.approx(5, abs=0.15)


def test_progress_counts_every_download_segment_and_the_final_join(make_project, tmp_path):
    clip = {"youtubeId": "aaaaaaaaaaa", "start": 0}
    path = make_project([intro(seconds=2), song(1, seconds=3, clip=clip), song(2, seconds=3, clip=clip), outro(seconds=2)])
    events = []

    run_job(path, tmp_path / "out.mp4", downloader=FakeDownloader(), progress=events.append)

    # 2 個片段＋4 個段落＋輸出 mp4＝7 步
    assert [(e.stage, e.current, e.total, e.done, e.steps) for e in events] == [
        ("download", 1, 2, 0, 7),
        ("download", 2, 2, 1, 7),
        ("compose", 1, 4, 2, 7),
        ("compose", 2, 4, 3, 7),
        ("compose", 3, 4, 4, 7),
        ("compose", 4, 4, 5, 7),
        ("join", 1, 1, 6, 7),
        ("done", 1, 1, 7, 7),
    ]
    assert [e.message for e in events[:-1]] == [
        "下載片段 1 / 2：aaaaaaaaaaa",
        "下載片段 2 / 2：aaaaaaaaaaa",
        "合成段落 1 / 4",
        "合成段落 2 / 4",
        "合成段落 3 / 4",
        "合成段落 4 / 4",
        "輸出 mp4",
    ]


def test_failed_clips_still_produce_output_and_are_listed(make_project, tmp_path):
    path = make_project([
        song(1, seconds=3, clip={"youtubeId": "aaaaaaaaaaa", "start": 0}),
        song(2, seconds=3, clip={"youtubeId": "bbbbbbbbbbb", "start": 0}),
    ])
    out = tmp_path / "out.mp4"

    result = run_job(path, out, downloader=FakeDownloader(fail={"bbbbbbbbbbb"}))

    assert result.exit_code == 3
    assert result.output == out and out.is_file()
    assert [(f.position, f.youtube_id, f.reason) for f in result.failures] == [(2, "bbbbbbbbbbb", "影片設成私人")]
    assert result.update_hint is None


def test_youtube_blocking_is_reported_as_blocked_without_output(make_project, tmp_path):
    path = make_project([song(1, seconds=3, clip={"youtubeId": "aaaaaaaaaaa", "start": 0})])
    out = tmp_path / "out.mp4"

    result = run_job(path, out, downloader=FakeDownloader(blocked=True))

    assert result.exit_code == 1
    assert result.output is None and not out.exists()
    assert result.blocked
    assert "YouTube 要求登入驗證" in result.error


def test_unusable_project_is_not_reported_as_blocked(make_project, tmp_path):
    path = make_project([song(1)], schema=2)

    result = run_job(path, tmp_path / "out.mp4")

    assert result.exit_code == 1
    assert result.error
    assert not result.blocked


def test_missing_input_file_is_an_error(tmp_path):
    result = run_job(tmp_path / "nope.zip")

    assert result.exit_code == 1
    assert "找不到檔案" in result.error


def test_output_defaults_to_next_to_the_input(make_project):
    path = make_project([song(1, seconds=2)])

    result = run_job(path)

    assert result.output == path.with_suffix(".mp4")
    assert result.output.is_file()


def test_packaged_app_with_every_clip_failing_suggests_latest_release(make_project, monkeypatch, tmp_path):
    from test_cli import frozen_app

    path = make_project([song(1, seconds=3, clip={"youtubeId": "bbbbbbbbbbb", "start": 0})])
    frozen_app(monkeypatch, tmp_path / "app")

    result = run_job(path, tmp_path / "out.mp4", downloader=FakeDownloader(fail={"bbbbbbbbbbb"}))

    assert "github.com/ryrr6466/CRITShowCase/releases" in result.update_hint


def test_job_prints_nothing(make_project, tmp_path, capsys):
    path = make_project([
        song(1, seconds=3, clip={"youtubeId": "aaaaaaaaaaa", "start": 0}),
        song(2, seconds=3, clip={"youtubeId": "bbbbbbbbbbb", "start": 0}),
    ])

    run_job(path, tmp_path / "out.mp4", downloader=FakeDownloader(fail={"bbbbbbbbbbb"}))
    run_job(path, tmp_path / "out2.mp4", downloader=FakeDownloader(blocked=True))

    assert capsys.readouterr() == ("", "")
