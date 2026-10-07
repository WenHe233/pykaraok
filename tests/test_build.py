from pathlib import Path

import pytest

from pykaraok import config
from pykaraok.aegi.templater import apply_templates
from pykaraok.ass.document import AssDocument
from pykaraok.build import source as srcmod
from pykaraok.build.luaflat import FlattenError, check_syntax, flatten
from pykaraok.build.project import build, ensure_k

ROOT = Path(__file__).resolve().parents[1]


def test_flatten_keeps_strings_and_comments():
    src = "-- note\nCOL = {a = '&HFF&', s = \"x -- y\", l = [[z]]} -- tail\nfunction f(x)\n  return x * 2\nend\n"
    out = flatten(src)
    assert "\n" not in out
    assert "--[[ note ]]" in out and "--[[ tail ]]" in out
    assert "\"x -- y\"" in out
    assert check_syntax(out) is None


def test_flatten_rejects_multiline_long_string():
    with pytest.raises(FlattenError):
        flatten("s = [[a\nb]]")


def test_comment_containing_brackets():
    out = flatten("-- a ]] b\nx = 1")
    assert check_syntax(out) is None


def test_source_parse():
    s = srcmod.parse("--@meta style=JP\n--@use core\n--@code once | 配置\nA = 1\n"
                     "--@template syl noblank layer=2 style=CN | 主体\n{\\an5\n  \\pos($scenter,$smiddle)}\n-- comment\n")
    assert s.meta == {"style": "JP"}
    assert s.uses == ["core"]
    code, tpl = s.blocks
    assert code.effect == "code once" and code.actor == "配置"
    assert tpl.effect == "template syl noblank"
    assert tpl.options == {"layer": "2", "style": "CN"}
    assert srcmod.block_text(tpl) == "{\\an5\\pos($scenter,$smiddle)}"


def test_all_fxlib_modules_compile():
    for p in config.FXLIB_DIR.glob("*.lua"):
        for b in srcmod.load(p).blocks:
            assert b.kind == "code" and b.code_class == "once", p
            assert check_syntax(srcmod.block_text(b), p.name) is None, p


def test_ensure_k_modes():
    e = {"text": "{\\an8}ab c", "start_time": 0, "end_time": 900}
    assert ensure_k(e, "line")[0] == "{\\k90}{\\an8}ab c"
    char, _ = ensure_k(e, "char")
    assert char.count("\\k") == 3 and char.startswith("{\\an8}")
    assert ensure_k({"text": "{\\k10}a", "start_time": 0, "end_time": 100}, "char")[0] == "{\\k10}a"


def test_build_starter(data_dir, tmp_path):
    out = tmp_path / "starter.ass"
    res = build(ROOT / "examples" / "starter" / "starter.fx.lua", data_dir / "lyrics.ass", out, k_mode="line")
    assert res.apply and res.apply["status"] == "ok", res.apply
    assert res.lyric_lines == 4
    doc = AssDocument.load(out)
    fx = [e for e in doc.events if e["effect"] == "fx"]
    assert len(fx) > 20
    # the untouched dialogue line survives
    assert any(e["text"] == "An ordinary dialogue line" and not e["comment"] for e in doc.events)
    # pressing Apply again in Aegisub gives the same file
    again = AssDocument.load(out)
    assert apply_templates(again).ok
    assert again.to_text() == doc.to_text()


def test_build_reorders_code_once_for_50_line_rule(tmp_path, data_dir):
    lines = ["--@meta style=JP"]
    for i in range(55):
        lines += [f"--@code once | c{i}", f"V{i} = {i}"]
    lines += ["--@template syl noblank", "!V3!"]
    src = tmp_path / "many.fx.lua"
    src.write_text("\n".join(lines), encoding="utf-8")
    res = build(src, data_dir / "lyrics.ass", tmp_path / "o.ass", k_mode="line")
    assert res.first_template_event <= 50
    assert any("50" in w for w in res.warnings)
