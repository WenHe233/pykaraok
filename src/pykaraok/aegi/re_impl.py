"""aegisub.__re_impl backed by Python's re (Aegisub uses boost::u32regex, perl syntax).

The Lua glue (lua/re_impl.lua) hands out FFI objects shaped like the C++
module's, so Aegisub's own re.moon runs unchanged on top of it.

Semantics kept from libaegisub/lua/modules/re.cpp:
  * positions are UTF-8 byte offsets; search returns 1-based first and inclusive last
  * perl syntax defaults: ^ and $ match at line breaks and . matches newline,
    unless NO_MOD_M / NO_MOD_S are given; ICASE, MOD_S, MOD_X map to re flags
  * replace() understands $&, $`, $', $n, ${n}, $$ and backslash escapes
Differences: Python's regex dialect is used (possessive quantifiers, atomic
groups and \\p{..} classes behave as in Python 3.11+).
"""
from __future__ import annotations

import re

FLAGS = {"ICASE": 1, "NOSUB": 2, "COLLATE": 4, "NEWLINE_ALT": 8, "NO_MOD_M": 16, "NO_MOD_S": 32,
         "MOD_S": 64, "MOD_X": 128, "NO_EMPTY_SUBEXPRESSIONS": 256}


class _Text:
    """A Lua string decoded once, with byte <-> character offset maps."""

    def __init__(self, raw):
        if isinstance(raw, bytes):
            self.s = raw.decode("utf-8", "replace")
        else:
            self.s = raw
        b = 0
        self.c2b = []
        for ch in self.s:
            self.c2b.append(b)
            b += len(ch.encode("utf-8"))
        self.c2b.append(b)
        self.b2c = {bo: i for i, bo in enumerate(self.c2b)}

    def char_at(self, byte_off: int) -> int:
        if byte_off in self.b2c:
            return self.b2c[byte_off]
        # inside a multi-byte character: move to the next character start
        for i, bo in enumerate(self.c2b):
            if bo >= byte_off:
                return i
        return len(self.s)


class ReImpl:
    def __init__(self):
        self.patterns: dict[int, re.Pattern] = {}
        self.matches: dict[int, tuple] = {}
        self._next = 1
        self._text_cache: tuple | None = None

    def _text(self, s) -> _Text:
        if self._text_cache is not None and self._text_cache[0] == s:
            return self._text_cache[1]
        t = _Text(s)
        self._text_cache = (s, t)
        return t

    def _id(self) -> int:
        self._next += 1
        return self._next

    def compile(self, pattern, flags):
        f = 0
        flags = int(flags)
        f |= 0 if flags & FLAGS["NO_MOD_M"] else re.MULTILINE
        if flags & FLAGS["MOD_S"] or not flags & FLAGS["NO_MOD_S"]:
            f |= re.DOTALL
        if flags & FLAGS["ICASE"]:
            f |= re.IGNORECASE
        if flags & FLAGS["MOD_X"]:
            f |= re.VERBOSE
        if isinstance(pattern, bytes):
            pattern = pattern.decode("utf-8", "replace")
        try:
            pat = re.compile(pattern, f)
        except re.error as exc:
            return False, f"invalid regular expression: {exc}"
        i = self._id()
        self.patterns[i] = pat
        return True, i

    def free(self, i):
        self.patterns.pop(int(i), None)

    def search(self, i, s, start):
        t = self._text(s)
        m = self.patterns[int(i)].search(t.s, t.char_at(int(start)))
        if not m:
            return None
        return t.c2b[m.start()] + 1, t.c2b[m.end()]

    def match(self, i, s, start):
        t = self._text(s)
        start = int(start)
        m = self.patterns[int(i)].search(t.s, t.char_at(start))
        if not m:
            return None
        spans = []
        for g in range(0, (m.re.groups or 0) + 1):
            a, b = m.span(g)
            spans.append(None if a < 0 else (t.c2b[a] - start + 1, t.c2b[b] - start))
        k = self._id()
        self.matches[k] = spans
        return k

    def get_match(self, k, idx):
        spans = self.matches.get(int(k))
        idx = int(idx)
        if spans is None or idx >= len(spans) or spans[idx] is None:
            return None
        return spans[idx]

    def match_free(self, k):
        self.matches.pop(int(k), None)

    def replace(self, i, replacement, s, max_count):
        if isinstance(replacement, bytes):
            replacement = replacement.decode("utf-8", "replace")
        t = self._text(s)
        pat = self.patterns[int(i)]
        out, last, n = [], 0, 0
        max_count = int(max_count)
        for m in pat.finditer(t.s):
            if n >= max_count:
                break
            out.append(t.s[last:m.start()])
            out.append(_format(replacement, m, t.s))
            last = m.end()
            n += 1
        out.append(t.s[last:])
        return "".join(out)


def _format(fmt: str, m: re.Match, whole: str) -> str:
    out = []
    i = 0
    n = len(fmt)
    while i < n:
        c = fmt[i]
        if c == "$" and i + 1 < n:
            d = fmt[i + 1]
            if d == "$":
                out.append("$")
                i += 2
                continue
            if d == "&":
                out.append(m.group(0))
                i += 2
                continue
            if d == "`":
                out.append(whole[:m.start()])
                i += 2
                continue
            if d == "'":
                out.append(whole[m.end():])
                i += 2
                continue
            if d == "{":
                j = fmt.find("}", i)
                if j > 0 and fmt[i + 2:j].isdigit():
                    g = int(fmt[i + 2:j])
                    out.append(m.group(g) or "" if g <= (m.re.groups or 0) else "")
                    i = j + 1
                    continue
            if d.isdigit():
                j = i + 1
                while j < n and fmt[j].isdigit() and int(fmt[i + 1:j + 1]) <= (m.re.groups or 0):
                    j += 1
                g = int(fmt[i + 1:j]) if j > i + 1 else int(d)
                if j == i + 1:
                    j = i + 2
                out.append((m.group(g) or "") if g <= (m.re.groups or 0) else "")
                i = j
                continue
        if c == "\\" and i + 1 < n:
            d = fmt[i + 1]
            out.append({"n": "\n", "t": "\t", "r": "\r"}.get(d, d))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def make_re_impl(lua):
    from .. import config
    impl = ReImpl()
    src = (config.LUA_DIR / "re_impl.lua").read_text(encoding="utf-8")
    loader = lua.eval("function(src) return assert(loadstring(src, '@pykaraok/re_impl.lua')) end")
    flag_list = lua.table_from([{"name": k, "value": v} for k, v in FLAGS.items()], recursive=True)
    py = lua.table_from({
        "compile": impl.compile, "free": impl.free, "search": impl.search, "match": impl.match,
        "get_match": impl.get_match, "match_free": impl.match_free, "replace": impl.replace,
        "flags": flag_list,
    })
    return loader(src)(py)
