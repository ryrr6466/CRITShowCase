"""seam：GUI 進入點，以及視窗建得起來（smoke test，不驅動按鈕）。"""
import sys

import pytest

from critshowcase import gui


def new_tk():
    tkinter = pytest.importorskip("tkinter")
    try:
        return tkinter.Tk()
    except tkinter.TclError as error:  # 沒有顯示器的環境
        pytest.skip(f"Tk 不能用：{error}")


@pytest.fixture
def root():
    window = new_tk()
    window.withdraw()
    yield window
    window.destroy()


@pytest.fixture
def tk_available():
    """main() 自己建主視窗；mainloop 要等所有主視窗都關掉，這裡探完就關。"""
    new_tk().destroy()


def test_main_window_builds(root, make_project, tmp_path):
    from critshowcase.cookies import CookieStore
    from critshowcase.gui.app import App

    App(root, source=make_project([]), cookie_store=CookieStore(tmp_path / "userdata"))
    root.update_idletasks()


def test_without_tkinter_explains_and_exits_with_error(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "tkinter", None)

    assert gui.main([]) == 1

    assert "tkinter" in capsys.readouterr().err


def test_cookie_tutorial_window_builds(root):
    from critshowcase.gui.tutorial import TutorialWindow

    TutorialWindow(root, on_import=lambda parent: None)
    root.update_idletasks()


def test_smoke_switch_opens_the_window_and_closes_it(tk_available, monkeypatch):
    """免安裝版的煙霧測試用：設了 CRITSHOWCASE_GUI_SMOKE 時視窗開起來後自己關掉，結束碼 0。"""
    monkeypatch.setenv("CRITSHOWCASE_GUI_SMOKE", "1")

    assert gui.main([]) == 0
