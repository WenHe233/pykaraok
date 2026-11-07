"""The Lua environment a script gets: Lua 5.2 compatibility and how it finds other files."""
import pytest

from pykaraok.aegi.runtime import AegiRuntime


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
