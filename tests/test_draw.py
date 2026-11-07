"""Glyph drawings must land where libass draws the text itself."""
import shutil

import numpy as np
import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from PIL import Image

from pykaraok.draw.compose import Part, compose, path_to_ass, shapely_to_ass
from pykaraok.draw.glyphs import resolve_face, text_drawing
from pykaraok.render import ffmpeg as rf
from test_fonts import make_font

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 640
PlayResY: 360
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: T,Arial,80,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _render(tmp_path, name, text):
    p = tmp_path / f"{name}.ass"
    p.write_text(HEADER + f"Dialogue: 0,0:00:00.00,0:00:05.00,T,,0,0,0,,{text}\n", encoding="utf-8")
    out = tmp_path / f"{name}.png"
    src = rf.Source(None, "black", (640, 360), (25, 1))
    rf.frame(p, 1.0, out, src)
    return np.asarray(Image.open(out).convert("L"), np.float32) / 255


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_text_drawing_matches_rendered_text(tmp_path):
    face = resolve_face("Arial")
    drawing, width = text_drawing(face, "Ag", 80)
    a = _render(tmp_path, "text", "{\\pos(100,100)}Ag")
    b = _render(tmp_path, "draw", "{\\pos(100,100)\\p1}" + drawing)
    ma, mb = a > 0.5, b > 0.5
    iou = (ma & mb).sum() / (ma | mb).sum()
    assert iou > 0.93, iou
    ya, xa = np.nonzero(ma)
    yb, xb = np.nonzero(mb)
    assert abs(xa.mean() - xb.mean()) < 1.0 and abs(ya.mean() - yb.mean()) < 1.0


def _font_with_spaces(path):
    """Cell height 1000 units; A is 600 units wide, a space 300 and U+3000 1000."""
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder([".notdef", "A", "space", "uni3000"])
    fb.setupCharacterMap({ord("A"): "A", 0x20: "space", 0x3000: "uni3000"})
    pen = TTGlyphPen(None)
    pen.moveTo((100, 0))
    pen.lineTo((100, 700))
    pen.lineTo((500, 700))
    pen.lineTo((500, 0))
    pen.closePath()
    box, empty = pen.glyph(), TTGlyphPen(None).glyph()
    fb.setupGlyf({".notdef": box, "A": box, "space": empty, "uni3000": empty})
    fb.setupHorizontalMetrics({".notdef": (600, 100), "A": (600, 100), "space": (300, 0), "uni3000": (1000, 0)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "PykSpaces", "styleName": "Regular", "fullName": "PykSpaces",
                       "uniqueFontIdentifier": "PykSpaces"})
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    fb.save(str(path))


def test_blanks_advance_by_their_own_width(tmp_path):
    """Every blank used to count as an ASCII space: U+3000 came out 3.4 times too narrow in YaHei."""
    path = tmp_path / "spaces.ttf"
    _font_with_spaces(path)
    face = resolve_face(str(path))
    assert text_drawing(face, "A A", 100)[1] == pytest.approx(150)
    assert text_drawing(face, "A　A", 100)[1] == pytest.approx(220)
    assert text_drawing(face, "A A", 100)[1] == pytest.approx(150)     # no such glyph: as a space
    # the second A starts where the blank ends
    assert text_drawing(face, "　A", 100)[0].startswith("m 110 ")


def test_blank_in_a_font_without_any(tmp_path):
    path = tmp_path / "no_space.ttf"
    make_font(path, "PykNoSpace")
    assert text_drawing(resolve_face(str(path)), "A A", 100)[1] == pytest.approx(60 + 100 / 3 + 60)


def test_compose_merges_parts():
    face = resolve_face("Arial")
    path, adv = compose(face, [Part("O"), Part("I", region=(0, 0, 0.5, 1), dx=0.2)], 60)
    d = path_to_ass(path)
    assert d.startswith("m ") and " b " in d
    assert adv > 0


def test_shapely_holes():
    from shapely.geometry import Polygon
    ring = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)], [[(3, 3), (7, 3), (7, 7), (3, 7)]])
    d = shapely_to_ass(ring)
    assert d.count("m ") == 2


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_layout_syl_box_matches_original(data_dir, tmp_path):
    """fxlib layout: each syllable at px.layout.syl_box lands where the original line draws it."""
    from pykaraok.build.project import build
    from pykaraok.qa.frames import steady_diff
    out = tmp_path / "layout.ass"
    res = build(data_dir / "layout.fx.lua", data_dir / "lyrics.ass", out)
    assert res.apply["status"] == "ok", res.apply["message"]
    src = rf.Source(None, "black", (1920, 1080), (25, 1))
    info = steady_diff(data_dir / "lyrics.ass", out, src)
    assert info["stripped_k"] is True
    # sub-pixel anti-aliasing differences only (libass kerns whole lines, syllables are placed one by one)
    assert all(r["max_diff"] < 64 for r in info["results"]), info["results"]
