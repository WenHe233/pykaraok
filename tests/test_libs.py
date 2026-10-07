"""Aegisub Lua libraries inside the template environment (Yutils vendored; ILL via `pykaraok setup libs`)."""
import pytest

from pykaraok import config, libs
from pykaraok.aegi.runtime import AegiRuntime, RunOptions
from pykaraok.aegi.templater import apply_templates
from pykaraok.ass.document import AssDocument


@pytest.fixture(scope="module")
def ev():
    rt = AegiRuntime()
    return rt.lua.eval


def test_yutils_text_to_shape_and_pixels(ev):
    shape = ev("require('Yutils').decode.create_font('Arial', false, false, false, false, 40).text_to_shape('A')")
    assert shape.startswith("m ") and len(shape) > 50
    assert ev("#require('Yutils').shape.to_pixels('m 0 0 l 4 0 l 4 4 l 0 4')") == 16


def _has(mod):
    return libs.status().get(mod, "missing") != "missing"


@pytest.mark.skipif(not (_has("ILL") and _has("clipper2")), reason="run `pykaraok setup libs` first")
def test_ill_path_boolean_and_offset(ev):
    out = ev("(function() local ILL = require('ILL.ILL') "
             "local u = ILL.Path('m 0 0 l 100 0 l 100 100 l 0 100'):unite(ILL.Path('m 50 50 l 150 50 l 150 150 l 50 150')) "
             "return u:export() end)()")
    assert "150 150" in out
    off = ev("(function() local ILL = require('ILL.ILL') "
             "return ILL.Path('m 0 0 l 10 0 l 10 10 l 0 10'):offset(2, 'round'):export() end)()")
    assert off.startswith("m ") and "-2" in off


def test_yutils_inside_a_template(data_dir):
    text = (data_dir / "basic.ass").read_text(encoding="utf-8").replace(
        "function half(x) return x / 2 end",
        "function half(x) return x / 2 end Y = _G.require('Yutils')").replace(
        "template syl,{\\an5\\pos($scenter,$smiddle)\\t($sstart,$send,\\fscx120)\\bord!half(4)!}",
        "template syl noblank,{\\an7\\pos($sleft,$stop)\\p1}!Y.shape.filter(Y.decode.create_font(line.styleref.fontname,"
        " false, false, false, false, line.styleref.fontsize).text_to_shape(syl.text_stripped), function(x, y) return x, y end)!")
    doc = AssDocument.from_text(text)
    res = apply_templates(doc, options=RunOptions())
    assert res.ok, res.message
    fx = [e for e in doc.events if e["effect"] == "fx"]
    assert fx and all("\\p1}m " in e["text"] for e in fx)
