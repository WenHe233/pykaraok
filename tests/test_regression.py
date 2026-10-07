"""Re-apply the templates of earlier projects and compare with what was delivered.

The delivered files were produced by earlier one-off harnesses, so a few
known differences are allowed:
  * time_round: those harnesses truncated milliseconds; Aegisub (and pykaraok)
    round to the nearest centisecond, 5 ms up (agi::Time::operator int).
  * alma measured text with fontTools instead of GDI; with --metrics fonttools
    the positions agree to 0.1 px.

Set PYKARAOK_PROJECTS to the folder that holds the project folders.
"""
import zipfile

import pytest

from pykaraok.aegi.runtime import RunOptions
from pykaraok.aegi.templater import apply_templates
from pykaraok.ass.document import AssDocument
from pykaraok.qa.compare import compare_docs

from conftest import PROJECTS


@pytest.fixture(scope="session")
def fonts07(tmp_path_factory):
    z = PROJECTS / "kimishinu_07" / "与你相恋到生命尽头_字幕字体包.zip"
    if not z.exists():
        pytest.skip("kimishinu_07 font pack not found")
    out = tmp_path_factory.mktemp("fonts07")
    with zipfile.ZipFile(z) as zf:
        for i, info in enumerate(zf.infolist()):
            if info.filename.lower().endswith((".ttf", ".otf", ".ttc")):
                (out / f"{i}{info.filename[-4:]}").write_bytes(zf.read(info))
    return out


CASES = [
    # (id, template source, delivered reference, font dir key, metrics, allowed categories, max numeric delta)
    ("07_wash", "kimishinu_07/与你相恋到生命尽头07_晕染特效.ass", None, "fonts07", "auto", {"identical", "time_round"}, 0),
    ("07_grain", "kimishinu_07/与你相恋到生命尽头07_晕染特效_水彩颗粒.ass", None, "fonts07", "auto", {"identical", "time_round"}, 0),
    ("12_in_v1", "kimishinu_12_IN/12_IN_template.ass", "kimishinu_12_IN/12_IN_fx.ass", "fonts07", "auto", {"identical", "time_round"}, 0),
    ("12_in_v2", "kimishinu_12_IN/12_IN_v2_template.ass", "kimishinu_12_IN/12_IN_v2_fx.ass", "fonts07", "auto", {"identical", "time_round"}, 0),
    ("12_in_v2_cht", "kimishinu_12_IN/12_IN_v2_CHT_template.ass", "kimishinu_12_IN/12_IN_v2_CHT_fx.ass", "fonts07", "auto", {"identical", "time_round"}, 0),
    ("rrk", "rrk-ass/rrk_karaoke.ass", None, "rrk-ass", "auto", {"identical", "time_round"}, 0),
    ("alma", "alma/Live《A·I》插入曲_特效.ass", None, "alma", "fonttools", {"identical", "time_round", "numeric"}, 0.1001),
]


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_reproduces_delivered_fx(case, request):
    cid, src, ref, fonts, metrics, allowed, max_delta = case
    src_path = PROJECTS / src
    if not src_path.exists():
        pytest.skip(f"{src_path} not found")
    font_dir = request.getfixturevalue("fonts07") if fonts == "fonts07" else PROJECTS / fonts
    doc = AssDocument.load(src_path)
    res = apply_templates(doc, options=RunOptions(font_dirs=[font_dir], metrics=metrics))
    assert res.ok, res.message
    reference = AssDocument.load(PROJECTS / (ref or src))
    rep = compare_docs(reference, doc)
    assert rep.total_a == rep.total_b, rep.to_dict()
    assert set(rep.counts) <= allowed, rep.to_dict()
    assert rep.max_numeric_delta <= max_delta, rep.to_dict()
    assert rep.max_time_delta_ms <= 10
