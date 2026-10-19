"""seam：CLI main(argv) 的結束碼與訊息。"""
import os
import shutil
import sys
from pathlib import Path

import pytest

from conftest import duration, intro, outro, song, write_zip
from critshowcase.cli import main


def test_renders_exported_zip_next_to_it(make_project, tmp_path):
    folder = make_project([intro(seconds=2), song(1, seconds=3), outro(seconds=2)]).parent
    archive = write_zip(tmp_path / "critlog-chunithm-b50-video.zip", folder)

    code = main([str(archive)])

    assert code == 0
    assert duration(tmp_path / "critlog-chunithm-b50-video.mp4") == pytest.approx(7, abs=0.15)


def test_output_path_option(make_project, tmp_path):
    path = make_project([song(1, seconds=3)])
    out = tmp_path / "my.mp4"

    assert main([str(path), "-o", str(out)]) == 0
    assert out.is_file()


def test_unknown_schema_exits_with_reason(make_project, capsys):
    path = make_project([song(1)], schema=2)

    assert main([str(path)]) == 1
    assert "schema 2" in capsys.readouterr().err
    assert not path.with_suffix(".mp4").exists()


def test_missing_ffmpeg_exits_with_install_hint(make_project, monkeypatch, capsys):
    path = make_project([song(1)])
    monkeypatch.setenv("PATH", "")

    assert main([str(path)]) == 1
    assert "找不到 ffmpeg" in capsys.readouterr().err


def test_failed_downloads_are_listed_and_exit_nonzero(make_project, tmp_path, capsys):
    from conftest import FakeDownloader

    path = make_project([song(1, seconds=3, clip={"youtubeId": "bbbbbbbbbbb", "start": 0}), song(2, seconds=3)])
    out = tmp_path / "out.mp4"

    code = main([str(path), "-o", str(out)], downloader=FakeDownloader(fail={"bbbbbbbbbbb"}))

    assert code == 3
    assert out.is_file()
    err = capsys.readouterr().err
    assert "第 1 段" in err and "bbbbbbbbbbb" in err and "影片設成私人" in err


def test_shows_progress_and_output_location(make_project, tmp_path, capsys):
    from conftest import FakeDownloader

    clip = {"youtubeId": "aaaaaaaaaaa", "start": 0}
    path = make_project([intro(seconds=2), song(1, seconds=3, clip=clip), song(2, seconds=3, clip=clip), outro(seconds=2)])
    out = tmp_path / "out.mp4"

    assert main([str(path), "-o", str(out)], downloader=FakeDownloader()) == 0

    lines = capsys.readouterr().out
    assert "下載片段 1 / 2" in lines and "下載片段 2 / 2" in lines
    assert "合成段落 4 / 4" in lines
    assert f"完成：{out}" in lines


def test_help_mentions_refresh_option(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])

    assert "--refresh" in capsys.readouterr().out


def test_version_shows_critshowcase_and_yt_dlp_versions(capsys):
    from importlib.metadata import version

    with pytest.raises(SystemExit) as exit:
        main(["--version"])

    assert exit.value.code == 0
    out = capsys.readouterr().out
    assert f"critshowcase {version('critshowcase')}" in out
    assert f"yt-dlp {version('yt-dlp')}" in out


def test_youtube_blocking_every_download_stops_without_output(make_project, tmp_path, capsys):
    from conftest import FakeDownloader

    clip = {"youtubeId": "aaaaaaaaaaa", "start": 0}
    path = make_project([song(1, seconds=3, clip=clip), song(2, seconds=3, clip=clip)])
    out = tmp_path / "out.mp4"
    downloader = FakeDownloader(blocked=True)

    assert main([str(path), "-o", str(out)], downloader=downloader) == 1

    assert len(downloader.calls) == 1  # 第一個就停，不會每首都試
    assert not out.exists()
    assert "YouTube 要求登入驗證" in capsys.readouterr().err


# ---- 打包版（PyInstaller）：外部工具放在 exe 旁邊的 tools 資料夾 ----

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


def frozen_app(monkeypatch, folder, tools=True):
    """模擬打包版：sys.frozen 為真、exe 在 folder；tools=True 時 tools 資料夾放真的 ffmpeg／ffprobe。"""
    folder.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(folder / "critshowcase.exe"))
    if tools:
        (folder / "tools").mkdir()
        for source in (FFMPEG, FFPROBE):
            target = folder / "tools" / Path(source).name
            try:
                os.link(source, target)
            except OSError:
                shutil.copy2(source, target)
    return folder


def broken_tools_on_path(monkeypatch, folder):
    """PATH 上放一組一執行就失敗的 ffmpeg／ffprobe。"""
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("ffmpeg", "ffprobe"):
        if sys.platform == "win32":
            (folder / f"{name}.bat").write_text("@exit /b 1\n")
        else:
            script = folder / name
            script.write_text("#!/bin/sh\nexit 1\n")
            script.chmod(0o755)
    monkeypatch.setenv("PATH", str(folder))


def test_packaged_app_uses_ffmpeg_next_to_exe_without_path(make_project, monkeypatch, tmp_path):
    path = make_project([intro(seconds=2), song(1, seconds=3)])
    out = tmp_path / "out.mp4"
    frozen_app(monkeypatch, tmp_path / "app")

    with monkeypatch.context() as m:
        m.setenv("PATH", "")
        code = main([str(path), "-o", str(out)])

    assert code == 0
    assert duration(out) == pytest.approx(5, abs=0.15)


def test_packaged_app_prefers_its_own_ffmpeg_over_path(make_project, monkeypatch, tmp_path):
    path = make_project([song(1, seconds=3)])
    out = tmp_path / "out.mp4"
    frozen_app(monkeypatch, tmp_path / "app")

    with monkeypatch.context() as m:
        broken_tools_on_path(m, tmp_path / "broken")
        code = main([str(path), "-o", str(out)])

    assert code == 0
    assert out.is_file()


def test_packaged_app_missing_ffmpeg_says_install_is_incomplete(make_project, monkeypatch, tmp_path, capsys):
    path = make_project([song(1)])
    frozen_app(monkeypatch, tmp_path / "app", tools=False)
    monkeypatch.setenv("PATH", "")

    assert main([str(path)]) == 1

    err = capsys.readouterr().err
    assert "安裝不完整" in err
    assert "pip" not in err


def test_packaged_app_missing_yt_dlp_says_install_is_incomplete(make_project, monkeypatch, tmp_path, capsys):
    path = make_project([song(1, seconds=3, clip={"youtubeId": "aaaaaaaaaaa", "start": 0})])
    frozen_app(monkeypatch, tmp_path / "app")
    monkeypatch.setitem(sys.modules, "yt_dlp", None)

    assert main([str(path), "-o", str(tmp_path / "out.mp4")]) == 1

    err = capsys.readouterr().err
    assert "安裝不完整" in err and "yt-dlp" in err
    assert "pip" not in err


def test_every_clip_failing_suggests_updating_yt_dlp(make_project, tmp_path, capsys):
    from conftest import FakeDownloader

    path = make_project([song(1, seconds=3, clip={"youtubeId": "bbbbbbbbbbb", "start": 0})])

    assert main([str(path), "-o", str(tmp_path / "out.mp4")], downloader=FakeDownloader(fail={"bbbbbbbbbbb"})) == 3

    assert 'pip install -U "yt-dlp[default]"' in capsys.readouterr().err


def test_packaged_app_every_clip_failing_suggests_downloading_latest_release(make_project, monkeypatch, tmp_path, capsys):
    from conftest import FakeDownloader

    path = make_project([song(1, seconds=3, clip={"youtubeId": "bbbbbbbbbbb", "start": 0})])
    frozen_app(monkeypatch, tmp_path / "app")

    assert main([str(path), "-o", str(tmp_path / "out.mp4")], downloader=FakeDownloader(fail={"bbbbbbbbbbb"})) == 3

    err = capsys.readouterr().err
    assert "下載最新版" in err and "github.com/ryrr6466/CRITShowCase/releases" in err
    assert "pip" not in err


def test_some_clips_failing_does_not_suggest_updating(make_project, tmp_path, capsys):
    from conftest import FakeDownloader

    path = make_project([
        song(1, seconds=3, clip={"youtubeId": "aaaaaaaaaaa", "start": 0}),
        song(2, seconds=3, clip={"youtubeId": "bbbbbbbbbbb", "start": 0}),
    ])

    assert main([str(path), "-o", str(tmp_path / "out.mp4")], downloader=FakeDownloader(fail={"bbbbbbbbbbb"})) == 3

    assert "yt-dlp" not in capsys.readouterr().err
