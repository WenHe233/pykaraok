"""aegisub.re through Aegisub's own re.moon running on pykaraok's __re_impl."""
import pytest

from pykaraok.aegi.runtime import AegiRuntime


@pytest.fixture(scope="module")
def ev():
    rt = AegiRuntime()
    rt.lua.execute("re = require 'aegisub.re'")
    return rt.lua.eval


def test_find_and_positions_are_bytes(ev):
    assert ev("re.find('aあb', 'b')[1].first") == 5      # 'a' (1 byte) + 'あ' (3 bytes) -> byte 5
    assert ev("re.find('abcabc', 'b')[2].first") == 5


def test_match_groups(ev):
    assert ev("re.match('pos(10,20)', [[pos\\((\\d+),(\\d+)\\)]])[2].str") == "10"
    assert ev("re.match('pos(10,20)', [[pos\\((\\d+),(\\d+)\\)]])[3].str") == "20"
    assert ev("re.match('abc', 'x')") is None


def test_sub(ev):
    assert ev("re.sub('a-b-c', '-', '+')") == "a+b+c"
    assert ev("re.sub('a-b-c', '-', '+', 1)") == "a+b-c"
    assert ev("re.sub('k10 k20', [[k(\\d+)]], 'K$1')") == "K10 K20"
    assert ev("re.sub('abc', 'b', function(s) return s:upper() end)") == "aBc"


def test_split_and_flags(ev):
    t = ev("re.split('a, b,c', [[,\\s*]])")
    assert [t[i] for i in range(1, len(t) + 1)] == ["a", "b", "c"]
    assert ev("re.match('ABC', 'b', re.ICASE)[1].str") == "B"


def test_compiled_object(ev):
    assert ev("(function() local r = re.compile([[\\d+]]) return r:find('a12b345')[2].str end)()") == "345"


def test_invalid_pattern_raises(ev):
    ok, _ = ev("pcall(re.compile, '(')")
    assert ok is False


def test_unicode_case(ev):
    assert ev("require('aegisub.unicode').to_upper_case('straße')") == "STRASSE"
