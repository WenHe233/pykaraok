import re

import pytest

from pykaraok.aegi.runtime import AegiRuntime, RunOptions
from pykaraok.aegi.templater import apply_templates
from pykaraok.ass.document import AssDocument, format_event


def load(data_dir, name="basic.ass"):
    return AssDocument.load(data_dir / name)


def test_apply_basic(data_dir):
    doc = load(data_dir)
    res = apply_templates(doc)
    assert res.ok, res.message
    assert res.can_template is True
    fx = [e for e in doc.events if e["effect"] == "fx"]
    # syllable 0 is the empty placeholder of parse_karaoke_data; without `noblank`
    # kara-templater emits a line for it, as Aegisub does
    assert len(fx) == 8
    assert fx[0]["text"].endswith("}")
    first = fx[1]
    assert first["start_time"] == 1000 and first["end_time"] == 4000
    assert first["text"].endswith("ka")
    m = re.search(r"\\pos\(([\d.]+),([\d.]+)\)", first["text"])
    assert m, first["text"]
    assert "\\t(0,500,\\fscx120)" in first["text"]
    assert "\\bord2" in first["text"]


def test_reapply_is_idempotent(data_dir, tmp_path):
    doc = load(data_dir)
    assert apply_templates(doc).ok
    once = doc.to_text()
    doc2 = AssDocument.from_text(once)
    assert apply_templates(doc2).ok
    assert doc2.to_text() == once


def test_untouched_lines_are_written_verbatim(data_dir):
    doc = load(data_dir)
    assert apply_templates(doc).ok
    text = doc.to_text()
    assert "; test file for pykaraok" in text
    raw = (data_dir / "basic.ass").read_text(encoding="utf-8").splitlines()
    for ln in raw:
        if ln.startswith("Comment:"):
            assert ln in text


def test_fifty_line_rule(data_dir):
    doc = load(data_dir)
    code = [e for e in doc.events if e["effect"] == "code once"][0]
    tpl = [e for e in doc.events if e["effect"].startswith("template")][0]
    kara = [e for e in doc.events if e["effect"] == "karaoke"][0]
    doc.events = [dict(kara, raw=None) for _ in range(55)] + [code, tpl]
    res = apply_templates(doc)
    assert res.ok
    assert res.can_template is False
    assert any("50" in w for w in res.warnings)


def test_script_error_is_reported(data_dir):
    doc = load(data_dir)
    for e in doc.events:
        if e["effect"] == "code once":
            e["text"] = "this is not lua"
            e.pop("raw", None)
    res = apply_templates(doc)
    assert not res.ok
    assert res.status in ("error", "cancelled")


class TestSubsObject:
    @pytest.fixture
    def rt(self, data_dir):
        return AegiRuntime(load(data_dir))

    def ev(self, rt, code):
        return rt.lua.eval(code)

    def test_len_and_groups(self, rt):
        g = rt.lua.globals()
        g.SUBS = rt.api.subs
        assert rt.lua.eval("#SUBS") == rt.lua.eval("SUBS.n") == 4 + 1 + 4
        assert rt.lua.eval("SUBS[1].class") == "info"
        assert rt.lua.eval("SUBS[5].class") == "style"
        assert rt.lua.eval("SUBS[5].color1") == "&H00FFFFFF&"

    def test_append_goes_after_same_group(self, rt):
        g = rt.lua.globals()
        g.SUBS = rt.api.subs
        rt.lua.execute("local s = SUBS[5]; s.name = 'Two'; SUBS.append(s)")
        assert rt.lua.eval("SUBS[6].name") == "Two"
        rt.lua.execute("local i = SUBS[1]; i.key = 'Foo'; SUBS.append(i)")
        assert rt.lua.eval("SUBS[5].key") == "Foo"

    def test_insert_delete_range(self, rt):
        g = rt.lua.globals()
        g.SUBS = rt.api.subs
        n = rt.lua.eval("#SUBS")
        rt.lua.execute("local l = SUBS[#SUBS]; l.text = 'X'; SUBS.insert(#SUBS, l)")
        assert rt.lua.eval("SUBS[#SUBS - 1].text") == "X"
        rt.lua.execute("SUBS.delete({#SUBS - 1})")
        assert rt.lua.eval("#SUBS") == n
        rt.lua.execute("SUBS.deleterange(#SUBS - 1, #SUBS)")
        assert rt.lua.eval("#SUBS") == n - 2
        rt.lua.execute("SUBS[0] = SUBS[#SUBS]")
        assert rt.lua.eval("#SUBS") == n - 1
        rt.lua.execute("SUBS[#SUBS] = nil")
        assert rt.lua.eval("#SUBS") == n - 2

    def test_out_of_range_and_bad_index(self, rt):
        g = rt.lua.globals()
        g.SUBS = rt.api.subs
        ok, msg = rt.lua.eval("pcall(function() return SUBS[1000] end)")
        assert ok is False and "out-of-range" in msg
        ok, msg = rt.lua.eval("pcall(function() return SUBS.nonsense end)")
        assert ok is False and "Invalid indexing" in msg

    def test_ipairs(self, rt):
        g = rt.lua.globals()
        g.SUBS = rt.api.subs
        assert rt.lua.eval("(function() local n = 0 for i, l in ipairs(SUBS) do n = i end return n end)()") == rt.lua.eval("#SUBS")

    def test_written_times_are_truncated_and_clamped(self, rt):
        g = rt.lua.globals()
        g.SUBS = rt.api.subs
        rt.lua.execute("local l = SUBS[#SUBS]; l.start_time = 1234.9; l.end_time = -5; SUBS[#SUBS] = l")
        assert rt.lua.eval("SUBS[#SUBS].start_time") == 1234
        assert rt.lua.eval("SUBS[#SUBS].end_time") == 0

    def test_text_extents(self, rt):
        g = rt.lua.globals()
        g.SUBS = rt.api.subs
        w, h, d, e = rt.lua.eval("aegisub.text_extents(SUBS[5], 'karaoke')")
        assert 100 < w < 250 and 40 < h < 60


def test_extradata_roundtrip():
    text = """[Script Info]
ScriptType: v4.00+
PlayResX: 640
PlayResY: 360

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Comment: 0,0:00:00.00,0:00:00.00,Default,,0,0,0,template syl,!syl.text!
Comment: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,karaoke,{=0}{\\k50}a{\\k50}b

[Aegisub Extradata]
Data: 0,_aegi_folddata,e0;1;1
"""
    doc = AssDocument.from_text(text)
    assert doc.events[1]["extra_ids"] == [0]
    assert apply_templates(doc).ok
    out = doc.to_text()
    assert "Data: 0,_aegi_folddata,e0;1;1" in out
    fx = [format_event(e) for e in doc.events if e["effect"] == "fx"]
    # kara-templater copies the line table including `extra`, so fx lines carry the id too
    assert all("{=0}" in f for f in fx)
