"""A font folder means the font files directly in it, for every consumer: default
discovery, --fonts, both measuring backends and the fontsdir handed to libass.

Project folders may keep whole font collections in subfolders; scanning those
made every render of one project take ~20 s.
"""
import json
import shutil
import sys

import numpy as np
import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from PIL import Image

from pykaraok import fonts
from pykaraok.cli import main
from pykaraok.cli_more import default_fonts
from pykaraok.metrics import make_metrics

ASS = """[Script Info]
ScriptType: v4.00+
PlayResX: 640
PlayResY: 360

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Top,PykTop,80,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Nested,PykNested,80,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:05.00,Top,,0,0,0,,{\\pos(100,100)}A
Dialogue: 0,0:00:00.00,0:00:05.00,Nested,,0,0,0,,{\\pos(400,100)}A
"""


def make_font(path, family):
    """A TrueType font whose A is a solid box 0.6 em wide, so a render shows which font drew it."""
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder([".notdef", "A"])
    fb.setupCharacterMap({ord("A"): "A"})
    pen = TTGlyphPen(None)
    pen.moveTo((100, 0))
    pen.lineTo((100, 700))
    pen.lineTo((500, 700))
    pen.lineTo((500, 0))
    pen.closePath()
    box = pen.glyph()
    fb.setupGlyf({".notdef": box, "A": box})
    fb.setupHorizontalMetrics({".notdef": (600, 100), "A": (600, 100)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    # GDI refuses a font without a full name and a unique ID
    fb.setupNameTable({"familyName": family, "styleName": "Regular", "fullName": family,
                       "uniqueFontIdentifier": family})
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    fb.save(str(path))


@pytest.fixture
def project(tmp_path, monkeypatch):
    """x.ass with PykTop next to it and PykNested in a subfolder, like a font collection."""
    monkeypatch.setenv("PYKARAOK_CACHE", str(tmp_path / "cache"))
    folder = tmp_path / "project"
    (folder / "collection").mkdir(parents=True)
    make_font(folder / "top.ttf", "PykTop")
    make_font(folder / "collection" / "nested.ttf", "PykNested")
    ass = folder / "x.ass"
    ass.write_text(ASS, encoding="utf-8", newline="\n")
    return ass


def test_default_discovery_skips_subfolders(project):
    found = default_fonts(project, None)
    assert found == [project.resolve().parent]
    assert [f.name for f in fonts.font_files(found)] == ["top.ttf"]


@pytest.mark.parametrize("backend", ["gdi", "fonttools"])
def test_metrics_skip_subfolders(project, backend):
    if backend == "gdi" and sys.platform != "win32":
        pytest.skip("GDI is Windows only")
    m = make_metrics(backend, default_fonts(project, None))
    assert m.text_extents({"fontname": "PykTop", "fontsize": 50}, "AA")[:2] == (60.0, 50.0)
    assert not m.warnings
    m.text_extents({"fontname": "PykNested", "fontsize": 50}, "AA")
    assert len(m.warnings) == 1 and "PykNested" in m.warnings[0]


@pytest.mark.parametrize("explicit", [False, True], ids=["default", "--fonts DIR"])
def test_fonts_check_skips_subfolders(project, capsys, explicit):
    args = ["fonts", "check", str(project), "--json"] + (["--fonts", str(project.parent)] if explicit else [])
    rc = main(args)
    findings = json.loads(capsys.readouterr().out)["findings"]
    assert {f["font"]: f["level"] for f in findings} == {"PykTop": "info", "PykNested": "error"}
    assert rc == 1


def test_libass_fontsdir_holds_only_top_level_fonts(project):
    # the folder also holds x.ass and a subfolder, so its fonts are linked into the cache
    d = fonts.single_dir(default_fonts(project, None))
    assert d.parent.parent == project.parent.parent / "cache"
    assert [f.read_bytes() for f in d.iterdir()] == [(project.parent / "top.ttf").read_bytes()]
    only = project.parent.parent / "only_fonts"
    only.mkdir()
    shutil.copy(project.parent / "top.ttf", only)
    assert fonts.single_dir([only]) == only


def _box_fill(mask):
    """Share of lit pixels inside their bounding box: ~1 for PykTop's box, far less for a real A."""
    ys, xs = np.nonzero(mask)
    return mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1].mean() if len(ys) else 0.0


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
@pytest.mark.parametrize("merged", [False, True], ids=["default", "two --fonts"])
def test_render_skips_subfolders(project, tmp_path, merged):
    out = tmp_path / "frame.png"
    args = ["render", "frame", str(project), "--at", "1", "--no-video", "--bg", "black", "--width", "0",
            "-o", str(out)]
    if merged:  # several font sources are merged into one fontsdir
        other = tmp_path / "other"
        other.mkdir()
        make_font(other / "other.ttf", "PykOther")
        args += ["--fonts", str(project.parent), "--fonts", str(other)]
    assert main(args) == 0
    lit = np.asarray(Image.open(out).convert("L")) > 128
    assert _box_fill(lit[:, :320]) > 0.9   # PykTop
    assert _box_fill(lit[:, 320:]) < 0.8   # PykNested is not loaded: libass falls back to another font
