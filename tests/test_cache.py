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
