"""seam：GUI 匯入的 cookies（匯入、狀態、清除）。不連網。"""
from datetime import datetime, timedelta

import pytest

from critshowcase.cookies import CookieError, CookieStore

YOUTUBE_COOKIES = (
    "# Netscape HTTP Cookie File\n"
    ".youtube.com\tTRUE\t/\tTRUE\t1893456000\tSID\tyoutube-session\n"
    ".youtube.com\tTRUE\t/\tTRUE\t1893456000\tHSID\tyoutube-hsid\n"
)
OTHER_SITE_COOKIES = (
    "# Netscape HTTP Cookie File\n"
    ".example.com\tTRUE\t/\tFALSE\t1893456000\tsession\texample\n"
)


@pytest.fixture
def store(tmp_path):
    return CookieStore(tmp_path / "userdata")


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def test_nothing_imported_at_first(store):
    assert store.current() is None


def test_importing_a_youtube_cookies_file_remembers_it(store, tmp_path):
    exported = write(tmp_path / "cookies.txt", YOUTUBE_COOKIES)

    imported = store.import_file(exported)

    assert store.current() == imported
    assert imported.path.read_text(encoding="utf-8") == YOUTUBE_COOKIES
    assert abs(imported.imported_at - datetime.now()) < timedelta(minutes=1)


def test_a_file_that_is_not_netscape_cookies_is_rejected_and_keeps_the_old_one(store, tmp_path):
    old = store.import_file(write(tmp_path / "cookies.txt", YOUTUBE_COOKIES))
    wrong = write(tmp_path / "notes.json", '{"cookies": [{"name": "SID", "domain": ".youtube.com"}]}')

    with pytest.raises(CookieError, match="Netscape"):
        store.import_file(wrong)

    assert store.current() == old
    assert old.path.read_text(encoding="utf-8") == YOUTUBE_COOKIES


def test_cookies_without_youtube_are_rejected(store, tmp_path):
    with pytest.raises(CookieError, match="youtube.com"):
        store.import_file(write(tmp_path / "cookies.txt", OTHER_SITE_COOKIES))

    assert store.current() is None


def test_missing_file_is_rejected(store, tmp_path):
    with pytest.raises(CookieError, match="找不到"):
        store.import_file(tmp_path / "nope.txt")


def test_clearing_forgets_the_imported_cookies(store, tmp_path):
    imported = store.import_file(write(tmp_path / "cookies.txt", YOUTUBE_COOKIES))

    store.clear()

    assert store.current() is None
    assert not imported.path.exists()
    store.clear()  # 沒有匯入時清除也沒關係


def test_imported_copy_is_used_even_after_the_exported_file_is_deleted(store, tmp_path):
    from critshowcase.download import YtDlpDownloader

    exported = write(tmp_path / "cookies.txt", YOUTUBE_COOKIES)
    imported = store.import_file(exported)
    exported.unlink()

    downloader = YtDlpDownloader(cookies=store.current().path)

    assert downloader.cookie_file == imported.path


def test_import_time_survives_yt_dlp_saving_rotated_cookies(store, tmp_path):
    """yt-dlp 每次結束都會把 cookies 寫回檔案；顯示的匯入時間不能跟著變。"""
    import os
    import time

    imported = store.import_file(write(tmp_path / "cookies.txt", YOUTUBE_COOKIES))
    later = time.time() + 3600
    os.utime(imported.path, (later, later))

    assert store.current().imported_at == imported.imported_at
