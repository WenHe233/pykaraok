"""Frame times reported by stream_frames (check --jumps) and render sheet are the times libass
rendered, and `render frame --at` with such a time shows the same frame, with or without a video.

Frame k is the k-th frame of the frame rate's grid (k * 1001/24000 s at 23.976 fps); a time
means the first frame at or after it.
"""
import shutil
import subprocess

import numpy as np
import pytest
from PIL import Image

from pykaraok.cli import main
from pykaraok.qa.frames import stream_frames
from pykaraok.render import ffmpeg as rf

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

# a full-screen box from 1000 ms
BOX = "Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,{\\an7\\pos(0,0)\\p1}m 0 0 l 1920 0 l 1920 1080 l 0 1080\n"
# a 40 px box whose left edge is at 0.3 px per ms: 12.5 px per frame at 23.976 fps
MOVE = "Dialogue: 0,0:00:00.00,0:00:05.00,Default,,0,0,0,,{\\an7\\move(0,0,600,0,0,2000)\\p1}m 0 0 l 40 0 l 40 40 l 0 40\n"


def _ass(tmp_path, w, h, event):
    p = tmp_path / "x.ass"
    p.write_text(HEADER.format(w=w, h=h) + event, encoding="utf-8", newline="\n")
    return p


@pytest.fixture(scope="module")
def black_video(tmp_path_factory):
    """Black 640x360 at 23.976 fps in MKV, which stores pts as whole ms (frame 12 at 501 ms, not 500.5)."""
    out = tmp_path_factory.mktemp("video") / "black.mkv"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                    "-i", "color=black:s=640x360:r=24000/1001:d=4", "-c:v", "ffv1", str(out)], check=True)
    return out


def _source(video, black_video):
    return rf.Source.make(black_video, "black") if video else rf.Source(None, "black", (640, 360))


def _left(img) -> int:
    """Left edge of the lit pixels."""
    return int(np.nonzero((np.asarray(img).max(axis=-1) > 100).any(axis=0))[0][0])


@pytest.mark.parametrize("fps", [(24000, 1001), (30000, 1001), (25, 1), (60000, 1001), (120, 1)])
def test_first_frame_inverts_frame_time(fps):
    """A frame time rounded to ms either way (reports, MKV pts) maps back to its frame."""
    src = rf.Source(None, "black", fps=fps)
    for k in range(0, 200000, 97):
        t = src.frame_time(k)
        assert src.first_frame(round(t, 3)) == k
        assert [src.first_frame(t + d) for d in (-0.0005, 0.0, 0.0005, 0.0006)] == [k, k, k, k + 1]


@needs_ffmpeg
@pytest.mark.parametrize("t0", [0.46, 0.5, 0.9, 0.96])
@pytest.mark.parametrize("video", [False, True], ids=["colour", "video"])
def test_first_lit_frame_is_first_frame_after_start(tmp_path, black_video, video, t0):
    """The box starts at 1000 ms: frame 24 at 1001 ms is the first one showing it, whatever t0 is.

    Before the fix the colour source reported 1042.2 ms for t0 = 0.5 (setpts truncated t0
    to a whole frame) and the video 960.5 ms for t0 = 0.46 (t0 + i / fps).
    """
    ass = _ass(tmp_path, 1920, 1080, BOX)
    src = rf.Source.make(black_video, "black") if video else rf.Source(None, "black")
    frames = list(stream_frames(ass, t0, t0 + 1.0, src, width=64))
    lit = [t for t, img in frames if img.max() > 100]
    assert round(lit[0] * 1000, 3) == 1001.0
    assert all(t >= 1.0 for t in lit)
    k0 = src.first_frame(t0)
    assert [t for t, _ in frames] == [(k0 + i) * 1001 / 24000 for i in range(len(frames))]


@needs_ffmpeg
@pytest.mark.parametrize("video", [False, True], ids=["colour", "video"])
def test_reported_time_renders_the_same_frame(tmp_path, black_video, video):
    """Each frame shows the box where libass puts it at the frame's time, and `render frame --at`
    with that time rounded to ms (as check --jumps reports it) renders the same frame.

    t0 = 0.48 lies halfway between frames 11 and 12, where the old times were off by 21 ms (6 px).
    """
    ass = _ass(tmp_path, 640, 360, MOVE)
    frames = list(stream_frames(ass, 0.48, 0.75, _source(video, black_video), width=640))
    where = ["--video", str(black_video)] if video else ["--no-video", "--bg", "black"]
    for t, img in frames:
        assert abs(_left(img) - 0.3 * t * 1000) < 1.5, t
        out = tmp_path / "f.png"
        assert main(["render", "frame", str(ass), "--at", str(round(t, 3)), "--width", "0", "-o", str(out)]
                    + where) == 0
        assert abs(_left(Image.open(out).convert("RGB")) - _left(img)) <= 1, t
    assert [t for t, _ in frames] == [k * 1001 / 24000 for k in range(12, 18)]


@needs_ffmpeg
@pytest.mark.parametrize("video", [False, True], ids=["colour", "video"])
def test_sheet_times_are_frame_times(tmp_path, black_video, video):
    """Each tile shows the first frame at or after its sample time, and "times" are those frames' times."""
    ass = _ass(tmp_path, 640, 360, MOVE)
    src = _source(video, black_video)
    out = tmp_path / "sheet.png"
    info = rf.sheet(ass, 0.48, 0.75, out, src, step=0.05, cols=8, width=320, label=False)
    # 0.48 0.53 0.58 0.63 0.68 0.73 s; frame 15 (625.6 ms) is skipped
    assert info["times"] == [round(k * 1001 / 24000, 3) for k in (12, 13, 14, 16, 17, 18)]
    img = np.asarray(Image.open(out).convert("RGB"))
    for i, t in enumerate(info["times"]):
        tile = img[:, i * 322:i * 322 + 320]
        assert abs(_left(tile) - 0.15 * t * 1000) < 1.5, t
