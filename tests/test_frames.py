"""Render-based checks: a failing ffmpeg must not look like a range without problems."""
import shutil
import subprocess
import sys
import threading
import tracemalloc

import pytest

from pykaraok.cli import main
from pykaraok.qa.frames import find_jumps, stream_frames
from pykaraok.render import ffmpeg as rf

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

ASS = """[Script Info]
ScriptType: v4.00+
PlayResX: 640
PlayResY: 360

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:05.00,Default,,0,0,0,fx,{\\an7\\pos(0,0)\\p1}m 0 0 l 100 0 l 100 100 l 0 100
"""
SRC = rf.Source(None, "black", (640, 360), (25, 1))


def _ass(tmp_path, extra=""):
    p = tmp_path / "x.ass"
    p.write_text(ASS + extra, encoding="utf-8", newline="\n")
    return p


def test_find_jumps_reports_a_one_frame_flash(tmp_path):
    # a second box that only frame 25 (1.00 s) shows
    ass = _ass(tmp_path, "Dialogue: 0,0:00:01.00,0:00:01.04,Default,,0,0,0,fx,"
                         "{\\an7\\pos(300,200)\\p1}m 0 0 l 100 0 l 100 100 l 0 100\n")
    info = find_jumps(ass, 0.5, 1.5, SRC, width=320)
    assert info["frames"] == 25
    assert info["count"] == 1
    jump = info["jumps"][0]
    assert jump["time"] == 1.0
    assert all(abs(got - want) <= 4 for got, want in zip(jump["box"], (300, 200, 400, 300))), jump


def test_find_jumps_ignores_steady_and_moving_lines(tmp_path):
    ass = _ass(tmp_path, "Dialogue: 0,0:00:00.00,0:00:05.00,Default,,0,0,0,fx,"
                         "{\\an7\\move(200,200,500,200)\\p1}m 0 0 l 100 0 l 100 100 l 0 100\n")
    info = find_jumps(ass, 0.5, 1.5, SRC, width=320)
    assert info["frames"] == 25
    assert info["count"] == 0


def test_find_jumps_does_not_hold_all_frames(tmp_path):
    """A list of all frames took 1.7 GB for three minutes at the default width."""
    tracemalloc.start()
    try:
        info = find_jumps(_ass(tmp_path), 0, 4, SRC, width=480)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert info["frames"] == 100
    assert peak < 20 * 480 * 270 * 3


def test_ffmpeg_failure_is_an_error(tmp_path):
    """It used to end the stream quietly: check --jumps reported 0 jumps in 0 frames."""
    with pytest.raises(RuntimeError, match="ffmpeg failed"):
        list(stream_frames(tmp_path / "missing.ass", 0, 1, SRC, width=64))
    with pytest.raises(RuntimeError, match="ffmpeg failed"):
        find_jumps(tmp_path / "missing.ass", 0, 1, SRC, width=64)


def test_failing_check_is_reported(tmp_path, capsys, monkeypatch):
    ass = _ass(tmp_path)
    monkeypatch.setattr(rf, "subtitle_filter", lambda *a, **k: "no_such_filter")
    assert main(["check", str(ass), "--jumps", "--no-video", "--json", "--fonts", str(tmp_path)]) == 1
    assert "ffmpeg failed" in capsys.readouterr().out


def test_stopping_early_is_not_a_failure(tmp_path):
    frames = stream_frames(_ass(tmp_path), 0, 4, SRC, width=64)
    next(frames)
    frames.close()


def test_a_lot_of_stderr_does_not_block_the_stream(tmp_path, monkeypatch):
    """ffmpeg would block on a full stderr pipe while we wait for frames (a damaged video
    logs decoding errors for every frame, and a pipe on Windows holds only 4 KB)."""
    talkative = ("import sys\n"
                 "sys.stderr.write('x' * 1000000)\n"
                 "sys.stderr.flush()\n"
                 f"sys.stdout.buffer.write(bytes({64 * 36 * 3 * 2}))\n")
    real = subprocess.Popen
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: real([sys.executable, "-c", talkative], **kw))
    got = []
    t = threading.Thread(target=lambda: got.extend(stream_frames(_ass(tmp_path), 0, 1, SRC, width=64)), daemon=True)
    t.start()
    t.join(30)
    assert not t.is_alive(), "stream_frames is stuck"
    assert len(got) == 2
