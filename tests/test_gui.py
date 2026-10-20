"""seam：GUI 進入點，以及視窗建得起來（smoke test，不驅動按鈕）。"""
import sys

import pytest

from critshowcase import gui


@pytest.fixture
def root():
    tkinter = pytest.importorskip("tkinter")
    try:
        window = tkinter.Tk()
    except tkinter.TclError as error:  # 沒有顯示器的環境
        pytest.skip(f"Tk 不能用：{error}")
    window.withdraw()
    yield window
    window.destroy()


def test_main_window_builds(root, make_project, tmp_path):
    from critshowcase.cookies import CookieStore
    from critshowcase.gui.app import App

    App(root, source=make_project([]), cookie_store=CookieStore(tmp_path / "userdata"))
    root.update_idletasks()


def test_without_tkinter_explains_and_exits_with_error(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "tkinter", None)

    assert gui.main([]) == 1

    assert "tkinter" in capsys.readouterr().err
