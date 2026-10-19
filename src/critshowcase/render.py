"""把影片專案合成 mp4（spec §8.3）。

每個段落先輸出成中間檔（影像 x264、聲音 PCM），最後依段落秒數精準裁切後串接、編成 mp4。
畫面 PNG 疊在最上面，工具自己不畫任何文字（ADR 0001）。
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from critshowcase import ffmpeg
from critshowcase.project import Project, Segment

FPS = 60
SAMPLE_RATE = 48000


def render(project: Project, output: Path, workdir: Path | None = None) -> None:
    ffmpeg.require_ffmpeg()
    output = Path(output)
    with tempfile.TemporaryDirectory(prefix="critshowcase-", dir=workdir) as tmp:
        parts = []
        for index, segment in enumerate(project.segments):
            part = Path(tmp) / f"{index:03d}.mkv"
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
        "-f", "lavfi", "-i", f"color=black:s={w}x{h}:r={FPS}:d={s}",
        "-loop", "1", "-framerate", str(FPS), "-t", str(s), "-i", str(segment.frame),
        "-f", "lavfi", "-t", str(s), "-i", f"anullsrc=r={SAMPLE_RATE}:cl=stereo",
        "-filter_complex", f"[1:v]scale={w}:{h}[f];[0:v][f]overlay=0:0:shortest=1,format=yuv420p[v]",
        "-map", "[v]", "-map", "2:a", "-t", str(s),
        *_intermediate_codecs(),
        str(part),
    ])


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
