"""The Lua environment a script gets: Lua 5.2 compatibility and how it finds other files."""
import shutil

import pytest

from pykaraok.aegi.runtime import AegiRuntime, RunOptions
from pykaraok.ass.document import AssDocument
from pykaraok.cli import main


@pytest.fixture(scope="module")
def ev():
    return AegiRuntime().lua.eval


def test_pairs_honours_the_metamethod(ev):
    # prelude.lua replaced a local named pairs, so the global one never saw __pairs
    assert ev("""(function()
        local t = setmetatable({}, {__pairs = function(t)
            return function(_, k) if not k then return 'key', 1 end end, t, nil
        end})
        local got = {}
        for k, v in pairs(t) do got[#got + 1] = k end
        return got[1]
    end)()""") == "key"


def test_ipairs_honours_the_metamethod(ev):
    assert ev("""(function()
        local t = setmetatable({}, {__ipairs = function(t)
            return function(_, i) if i == 0 then return 1, 'value' end end, t, 0
        end})
        local got = {}
        for i, v in ipairs(t) do got[i] = v end
        return got[1]
    end)()""") == "value"


def test_pairs_and_ipairs_on_plain_tables(ev):
    assert ev("(function() local n = 0 for k, v in pairs({a = 1, b = 2, 3}) do n = n + v end return n end)()") == 6
    assert ev("(function() local n = 0 for i, v in ipairs({1, 2, nil, 4}) do n = n + v end return n end)()") == 3
    ok, _ = ev("pcall(pairs, nil)")
    assert ok is False


@pytest.fixture
def macro(tmp_path, data_dir):
    """A macro folder with helper files, and the subtitle file in another folder."""
    folder = tmp_path / "macro"
    (folder / "sub").mkdir(parents=True)
    (folder / "helper.lua").write_text("HELPER = 'next to the script'\n", encoding="utf-8")
    (folder / "sub" / "rel.lua").write_text("REL = 'relative to the script'\n", encoding="utf-8")
    (folder / "modhelper.lua").write_text("return {v = 'required'}\n", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    shutil.copy(data_dir / "basic.ass", docs / "x.ass")
    return folder, docs / "x.ass"


def _load(macro, code, **options):
    folder, ass = macro
    script = folder / "m.lua"
    script.write_text(code + "\naegisub.register_macro('m', 'd', function() end)\n", encoding="utf-8")
    doc = AssDocument.load(ass)
    rt = AegiRuntime(doc, RunOptions(**options), script_path=doc.path)
    rt.load_script(script)
    return rt.lua.eval


def test_include_path_is_relative_to_the_script_not_the_subtitles(macro):
    """LuaScript::LuaInclude: `filepath = s->GetFilename().parent_path()/filename`."""
    assert _load(macro, "include('sub/rel.lua')")("REL") == "relative to the script"


def test_absolute_include(macro):
    folder, _ = macro
    assert _load(macro, f"include('{folder.as_posix()}/helper.lua')")("HELPER") == "next to the script"


def test_plain_include_and_require_look_next_to_the_script_first(macro, tmp_path):
    """Script::Script: `include_path.emplace_back(filename.parent_path())` before the others."""
    other = tmp_path / "other"
    other.mkdir()
    (other / "helper.lua").write_text("HELPER = 'in --include'\n", encoding="utf-8")
    (other / "only_here.lua").write_text("ONLY = 'in --include'\n", encoding="utf-8")
    ev = _load(macro, "include('helper.lua')\ninclude('only_here.lua')\nMOD = require('modhelper').v",
               include_dirs=[other])
    assert ev("HELPER") == "next to the script"
    assert ev("ONLY") == "in --include"
    assert ev("MOD") == "required"


def test_script_token_is_still_the_subtitle_folder(macro):
    _, ass = macro
    assert _load(macro, "")("aegisub.decode_path('?script/x')") == ass.parent.as_posix() + "/x"


def test_run_macro_with_a_relative_script_path(macro, monkeypatch, capsys):
    folder, ass = macro
    (folder / "m.lua").write_text("include('sub/rel.lua')\naegisub.register_macro('m', 'd', function() end)\n",
                                  encoding="utf-8")
    monkeypatch.chdir(folder)
    assert main(["run-macro", "m.lua", str(ass), "--list"]) == 0
    assert capsys.readouterr().out.strip() == "m"
