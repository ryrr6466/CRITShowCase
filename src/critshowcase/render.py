"""把影片專案合成 mp4（spec §8.3）。

每個段落先輸出成中間檔（影像 x264、聲音 PCM），最後依段落秒數精準裁切後串接、編成 mp4。
畫面 PNG 疊在最上面，工具自己不畫任何文字（ADR 0001）。
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from critshowcase import ffmpeg
from critshowcase.download import Downloader, YtDlpDownloader
from critshowcase.project import Project, Segment

FPS = 60
SAMPLE_RATE = 48000


def render(project: Project, output: Path, downloader: Downloader | None = None, workdir: Path | None = None) -> None:
    ffmpeg.require_ffmpeg()
    if downloader is None and any(s.clip for s in project.segments):
        downloader = YtDlpDownloader()
    output = Path(output)
    with tempfile.TemporaryDirectory(prefix="critshowcase-", dir=workdir) as tmp:
        clips_dir = Path(tmp) / "clips"
        clips_dir.mkdir()
        parts = []
        for index, segment in enumerate(project.segments):
            part = Path(tmp) / f"{index:03d}.mkv"
            if segment.clip and downloader:
                clip_file = downloader.fetch(segment.clip, segment.seconds, clips_dir)
                _clip_segment(project, segment, clip_file, part)
            else:
                _static_segment(project, segment, part)
            parts.append(part)
        # 先寫到暫存檔，完成才換上去，失敗時不留下半成品
        partial = Path(tmp) / "output.mp4"
        _join(project, parts, partial)
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(partial, output)


def _static_segment(project: Project, segment: Segment, part: Path) -> None:
    """畫面停留 seconds 秒、聲音靜音。PNG 的透明處（影片框）露出黑底。"""
    w, h, s = project.output.width, project.output.height, segment.seconds
    ffmpeg.run([
        *_background(w, h, s),
        *_frame_input(segment, s),
        *_silence(s),
        "-filter_complex", f"[1:v]scale={w}:{h}[f];[0:v][f]overlay=0:0:shortest=1,format=yuv420p[v]",
        "-map", "[v]", "-map", "2:a", "-t", str(s),
        *_intermediate_codecs(),
        str(part),
    ])


def _clip_segment(project: Project, segment: Segment, clip_file: Path, part: Path) -> None:
    """片段縮放進影片框（保持比例、置中、補黑邊），畫面疊在上面；片段不夠長就停在最後一格。"""
    assert segment.video_box is not None
    w, h, s = project.output.width, project.output.height, segment.seconds
    box = segment.video_box
    audio = ffmpeg.has_audio(clip_file)
    filters = [
        f"[1:v]scale={box.w}:{box.h}:force_original_aspect_ratio=decrease,setsar=1,fps={FPS}[c]",
        # eof_action=repeat：片段放完後停在最後一格
        f"[0:v][c]overlay=x={box.x}+({box.w}-overlay_w)/2:y={box.y}+({box.h}-overlay_h)/2:eof_action=repeat[b]",
        f"[2:v]scale={w}:{h}[f]",
        "[b][f]overlay=0:0,format=yuv420p[v]",
    ]
    if audio:
        filters.append(f"[1:a]aresample={SAMPLE_RATE},aformat=channel_layouts=stereo,apad,atrim=0:{s}[a]")
    ffmpeg.run([
        *_background(w, h, s),
        "-t", str(s), "-i", str(clip_file),
        *_frame_input(segment, s),
        *([] if audio else _silence(s)),
        "-filter_complex", ";".join(filters),
        "-map", "[v]", "-map", "[a]" if audio else "3:a", "-t", str(s),
        *_intermediate_codecs(),
        str(part),
    ])


def _background(w: int, h: int, s: float) -> list[str]:
    return ["-f", "lavfi", "-i", f"color=black:s={w}x{h}:r={FPS}:d={s}"]


def _frame_input(segment: Segment, s: float) -> list[str]:
    return ["-loop", "1", "-framerate", str(FPS), "-t", str(s), "-i", str(segment.frame)]


def _silence(s: float) -> list[str]:
    return ["-f", "lavfi", "-t", str(s), "-i", f"anullsrc=r={SAMPLE_RATE}:cl=stereo"]


def _intermediate_codecs() -> list[str]:
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-r", str(FPS), "-c:a", "pcm_s16le", "-ar", str(SAMPLE_RATE), "-ac", "2"]


def _join(project: Project, parts: list[Path], output: Path) -> None:
    inputs, filters, labels = [], [], []
    for i, (part, segment) in enumerate(zip(parts, project.segments)):
        s = segment.seconds
        inputs += ["-i", str(part)]
        filters.append(f"[{i}:v]trim=0:{s},setpts=PTS-STARTPTS[v{i}]")
        filters.append(f"[{i}:a]apad,atrim=0:{s},asetpts=PTS-STARTPTS[a{i}]")
        labels.append(f"[v{i}][a{i}]")
    filters.append(f"{''.join(labels)}concat=n={len(parts)}:v=1:a=1[v][a]")
    ffmpeg.run([
        *inputs,
        "-filter_complex", ";".join(filters),
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
        str(output),
    ])
