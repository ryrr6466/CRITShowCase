"""seam：CLI main(argv) 的結束碼與訊息。"""
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
