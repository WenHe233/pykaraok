import shutil
import struct
import wave

import numpy as np
import pytest

from pykaraok.ass.document import AssDocument
from pykaraok.text import cht


def test_convert_markup_keeps_tags_and_line_breaks():
    conv = {"这": "這", "说": "說"}.get
    f = lambda s: "".join(conv(c) or c for c in s)  # noqa: E731
    out = cht.convert_markup("{\\k10\\1c&H0000FF&}这{\\k20}说\\N这", f, [("說", "讲")])
    assert out == "{\\k10\\1c&H0000FF&}這{\\k20}讲\\N這"


def test_convert_doc_only_touches_chosen_styles(data_dir):
    pytest.importorskip("opencc")
    text = (data_dir / "lyrics.ass").read_text(encoding="utf-8")
    text = text.replace("the colour of the sky", "这是你的天空").replace("An ordinary dialogue line", "这行不转换")
    doc = AssDocument.from_text(text)
    rep = cht.convert_doc(doc, ["CN"], "s2twp", [("你", "妳")])
    assert rep.changed == 1
    assert any(e["text"] == "這是妳的天空" for e in doc.events)
    assert any(e["text"] == "这行不转换" for e in doc.events)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_beats_on_click_track(tmp_path):
    from pykaraok.audio.beats import estimate
    sr, bpm, first = 22050, 128.0, 0.37
    dur = 30.0
    y = np.zeros(int(sr * dur), np.float32)
    period = 60 / bpm
    t = first
    while t < dur - 0.1:
        i = int(t * sr)
        n = int(0.03 * sr)
        y[i:i + n] += np.sin(2 * np.pi * 120 * np.arange(n) / sr) * np.exp(-np.arange(n) / (0.008 * sr))
        t += period
    path = tmp_path / "click.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, v)) * 30000)) for v in y))
    r = estimate(path, 0, dur)
    assert abs(r["bpm"] - bpm) < 0.5, r
    # first beat within 25 ms (or one beat later)
    off = (r["first_beat_ms"] / 1000 - first) % period
    assert min(off, period - off) < 0.025, r
