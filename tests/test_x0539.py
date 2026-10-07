import re

import pytest

from pykaraok import config
from pykaraok.aegi.runtime import RunOptions
from pykaraok.ass.document import AssDocument
from pykaraok.build.project import build


def _installed():
    return (config.cache_dir() / "0x539" / "0x.KaraTemplater.moon").exists()


pytestmark = pytest.mark.skipif(not _installed(), reason="run `pykaraok setup 0x539` first")


def test_0x539_template(data_dir, tmp_path):
    out = tmp_path / "x.ass"
    res = build(data_dir / "x0539.fx.lua", data_dir / "lyrics.ass", out, lyric_styles=["JP", "CN"],
                run_options=RunOptions(seed=1))
    assert res.apply["status"] == "ok", res.apply["message"]
    doc = AssDocument.load(out)
    fx = [e for e in doc.events if e["effect"] == "fx"]
    by_layer = {}
    for e in fx:
        by_layer[e["layer"]] = by_layer.get(e["layer"], 0) + 1
    # line template (2 JP lines), 2 sparks per non-blank syllable (10 syllables),
    # `if is_long` syllables (>= 500 ms: 5), anystyle words (3 + 3 + 5 + 4)
    assert by_layer == {0: 2, 2: 20, 3: 5, 4: 15}
    line0 = next(e for e in fx if e["layer"] == 0)
    # mixin char with util.gbc from 0x.color: one \3c per character, red to blue
    assert line0["text"].startswith("{\\an8\\fad(200,200)\\3c&H0000FF&}s")
    assert line0["text"].endswith("{\\3c&HFF0000&}o")
    spark = next(e for e in fx if e["layer"] == 2)
    assert re.search(r"\\pos\([\d.]+,[\d.]+\)", spark["text"])
    # input lines are marked kara for this engine
    assert sum(1 for e in doc.events if e["effect"] == "kara") == 4


def test_0x539_seeded_runs_are_identical(data_dir, tmp_path):
    a, b = tmp_path / "a.ass", tmp_path / "b.ass"
    for out in (a, b):
        build(data_dir / "x0539.fx.lua", data_dir / "lyrics.ass", out, lyric_styles=["JP", "CN"],
              run_options=RunOptions(seed=7))
    assert a.read_bytes() == b.read_bytes()
