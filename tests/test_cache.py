"""seam：CachedDownloader 把下載過的片段留在快取，重跑時不再下載。"""
from pathlib import Path

import pytest

from critshowcase.cache import CachedDownloader
from critshowcase.download import DownloadError
from critshowcase.project import Clip

CLIP = Clip("dQw4w9WgXcQ", 12.0)


class CountingDownloader:
    """寫出內容可辨認的假片段，並記錄被呼叫幾次。"""

    def __init__(self, fail=False, interrupt=False):
        self.calls = 0
        self.fail = fail
        self.interrupt = interrupt

    def fetch(self, clip, seconds, dest):
        self.calls += 1
        path = Path(dest) / f"{clip.youtube_id}.mkv"
        path.write_bytes(f"{clip.youtube_id} {clip.start} {seconds} #{self.calls}".encode())
        if self.fail:
            raise DownloadError("影片已刪除或無法觀看")
        if self.interrupt:
            raise KeyboardInterrupt
        return path


def test_second_fetch_uses_cache(tmp_path):
    inner = CountingDownloader()
    cached = CachedDownloader(inner, tmp_path / "cache")

    first = cached.fetch(CLIP, 10, tmp_path / "a")
    second = cached.fetch(CLIP, 10, tmp_path / "b")

    assert inner.calls == 1
    assert second.read_bytes() == first.read_bytes()


def test_cache_survives_new_instance(tmp_path):
    inner = CountingDownloader()
    CachedDownloader(inner, tmp_path / "cache").fetch(CLIP, 10, tmp_path)

    CachedDownloader(inner, tmp_path / "cache").fetch(CLIP, 10, tmp_path)

    assert inner.calls == 1


@pytest.mark.parametrize(
    "clip, seconds",
    [(Clip("dQw4w9WgXcQ", 13.0), 10), (CLIP, 8), (CLIP, 10.5), (Clip("dQw4w9WgXcQ", 12.5), 10), (Clip("aaaaaaaaaaa", 12.0), 10)],
)
def test_different_clip_downloads_again(tmp_path, clip, seconds):
    inner = CountingDownloader()
    cached = CachedDownloader(inner, tmp_path / "cache")
    cached.fetch(clip, seconds, tmp_path)

    path = cached.fetch(CLIP, 10, tmp_path)

    assert inner.calls == 2
    assert path.read_bytes().endswith(b"#2")


def test_refresh_downloads_again_and_replaces_cache(tmp_path):
    inner = CountingDownloader()
    CachedDownloader(inner, tmp_path / "cache").fetch(CLIP, 10, tmp_path)

    refreshed = CachedDownloader(inner, tmp_path / "cache", refresh=True).fetch(CLIP, 10, tmp_path)
    later = CachedDownloader(inner, tmp_path / "cache").fetch(CLIP, 10, tmp_path)

    assert inner.calls == 2
    assert refreshed.read_bytes().endswith(b"#2")
    assert later.read_bytes().endswith(b"#2")


def test_interrupted_download_is_not_a_cache_hit(tmp_path):
    with pytest.raises(KeyboardInterrupt):
        CachedDownloader(CountingDownloader(interrupt=True), tmp_path / "cache").fetch(CLIP, 10, tmp_path)

    inner = CountingDownloader()
    CachedDownloader(inner, tmp_path / "cache").fetch(CLIP, 10, tmp_path)

    assert inner.calls == 1


def test_failed_download_is_not_cached(tmp_path):
    failing = CountingDownloader(fail=True)
    cached = CachedDownloader(failing, tmp_path / "cache")

    for _ in range(2):
        with pytest.raises(DownloadError):
            cached.fetch(CLIP, 10, tmp_path)

    assert failing.calls == 2


def test_start_seconds_differing_in_the_millisecond_download_again(tmp_path):
    inner = CountingDownloader()
    cached = CachedDownloader(inner, tmp_path / "cache")
    cached.fetch(Clip("dQw4w9WgXcQ", 1234.567), 10, tmp_path)

    cached.fetch(Clip("dQw4w9WgXcQ", 1234.568), 10, tmp_path)

    assert inner.calls == 2


@pytest.fixture
def make_unreadable():
    """讓目前使用者讀不到檔案（模擬系統管理員身分留下的快取），測試結束後還原。"""
    import getpass
    import os
    import subprocess
    import sys

    changed = []

    def make(path):
        if sys.platform == "win32":
            subprocess.run(["icacls", str(path), "/deny", f"{getpass.getuser()}:(R)"], check=True, capture_output=True)
        else:
            if os.geteuid() == 0:
                pytest.skip("root 讀得到任何檔案")
            os.chmod(path, 0)
        changed.append(path)
        with pytest.raises(PermissionError):
            Path(path).read_bytes()

    yield make
    for path in changed:
        if sys.platform == "win32":
            subprocess.run(["icacls", str(path), "/reset"], capture_output=True)
        else:
            os.chmod(path, 0o644)


def test_unreadable_cached_clip_is_downloaded_again(tmp_path, make_unreadable):
    inner = CountingDownloader()
    cached = CachedDownloader(inner, tmp_path / "cache")
    first = cached.fetch(CLIP, 10, tmp_path / "a")
    make_unreadable(first)

    again = cached.fetch(CLIP, 10, tmp_path / "b")

    assert inner.calls == 2
    assert again.read_bytes().endswith(b"#2")


def test_unwritable_cache_still_returns_the_clip(tmp_path):
    blocked = tmp_path / "cache"
    blocked.write_text("這是檔案，不是資料夾")  # 快取資料夾建不起來
    inner = CountingDownloader()
    dest = tmp_path / "dest"
    dest.mkdir()

    path = CachedDownloader(inner, blocked).fetch(CLIP, 10, dest)

    assert path.read_bytes().endswith(b"#1")
    assert path.parent == dest
