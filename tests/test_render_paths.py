"""Paths with characters that mean something to ffmpeg, in every place a path reaches it."""
import shutil

import numpy as np
import pytest
from PIL import Image

from pykaraok.render import ffmpeg as rf
from test_fonts import make_font

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

ASS = """[Script Info]
ScriptType: v4.00+
PlayResX: 320
PlayResY: 180

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,PykPath,80,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:05.00,Default,,0,0,0,,{\\pos(100,50)}A
"""

NAMES = ["it's", "a'b'c", "'", "a,b", "a;b", "a[b]", "a=b", "a b", "100%", "a%d", "a{b}", "日本語"]
SRC = rf.Source(None, "black", (320, 180), (25, 1))


def _lit(path) -> bool:
    return bool((np.asarray(Image.open(path).convert("L")) > 128).any())


def _box_fill(path) -> float:
    """Share of lit pixels inside their bounding box: ~1 for the test font's solid box."""
    lit = np.asarray(Image.open(path).convert("L")) > 128
    ys, xs = np.nonzero(lit)
    return lit[ys.min():ys.max() + 1, xs.min():xs.max() + 1].mean()


@pytest.fixture
def project(tmp_path, request):
    folder = tmp_path / request.param
    folder.mkdir()
    (folder / "x.ass").write_text(ASS, encoding="utf-8", newline="\n")
    return folder


@pytest.mark.parametrize("project", NAMES, indirect=True)
def test_subtitles_and_output_in_any_folder(project):
    """A quote used to fail with "Error opening output files", and %d named another folder."""
    out = project / "f.png"
    rf.frame(project / "x.ass", 1.0, out, SRC)
    assert _lit(out)
    sheet = project / "s.png"
    rf.sheet(project / "x.ass", 0.5, 1.5, sheet, SRC, step=0.5, width=160, label=False)
    assert _lit(sheet)


@pytest.mark.parametrize("project", NAMES, indirect=True)
def test_fontsdir_in_any_folder(project):
    """libass ignores a fontsdir it cannot open: a quote lost the fonts without any error."""
    fonts = project / "fonts"
    fonts.mkdir()
    make_font(fonts / "f.ttf", "PykPath")
    ass = project.parent / "plain.ass"     # only the fontsdir has the special characters
    ass.write_text(ASS, encoding="utf-8", newline="\n")
    out = project.parent / "f.png"
    rf.frame(ass, 1.0, out, SRC, font_dirs=[fonts])
    assert _box_fill(out) > 0.9


@pytest.mark.parametrize("name", ["a%d.png", "100%.png", "a%03d.png"])
def test_output_name_is_not_a_pattern(tmp_path, name):
    """a%d.png used to be reported as written while the frame went to a1.png."""
    src = tmp_path / "x.ass"
    src.write_text(ASS, encoding="utf-8", newline="\n")
    rf.frame(src, 1.0, tmp_path / name, SRC)
    rf.sheet(src, 0.5, 1.5, tmp_path / ("s" + name), SRC, step=0.5, width=160, label=False)
    assert sorted(p.name for p in tmp_path.glob("*.png")) == sorted([name, "s" + name])


def test_label_font_path_is_quoted(tmp_path):
    src = tmp_path / "x.ass"
    src.write_text(ASS, encoding="utf-8", newline="\n")
    rf.frame(src, 1.0, tmp_path / "f.png", SRC, label=True)
    assert _lit(tmp_path / "f.png")
