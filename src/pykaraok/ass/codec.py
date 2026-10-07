"""Value codecs that follow Aegisub's own implementation.

Sources (TypesettingTools/Aegisub @ 06d5f4b9):
  libaegisub/ass/time.cpp, include/libaegisub/ass/time.h
  libaegisub/ass/string_codec.cpp, libaegisub/ass/uuencode.cpp
  src/ass_style.cpp (UpdateData), libaegisub/common/color.cpp
"""
from __future__ import annotations

MAX_TIME = 10 * 60 * 60 * 1000 - 6


def clamp_time(ms: int) -> int:
    return max(0, min(int(ms), MAX_TIME))


def parse_time(text: str) -> int:
    """agi::Time(std::string_view): 'H:MM:SS.cc' -> milliseconds."""
    time = 0
    current = 0
    after_decimal = -1
    for c in text:
        if c == ":":
            time = time * 60 + current
            current = 0
        elif c in ".,":
            time = (time * 60 + current) * 1000
            current = 0
            after_decimal = 100
        elif not ("0" <= c <= "9"):
            continue
        elif after_decimal < 0:
            current = current * 10 + (ord(c) - 48)
        else:
            time += (ord(c) - 48) * after_decimal
            after_decimal //= 10
    if after_decimal < 0:
        time = (time * 60 + current) * 1000
    return clamp_time(time)


def round_cs(ms: int) -> int:
    """agi::Time::operator int: round to centiseconds, 5 ms rounds up."""
    return (ms + 5) - (ms + 5) % 10


def format_time(ms: int) -> str:
    """agi::Time::GetAssFormatted() for a value already clamped by agi::Time."""
    t = round_cs(clamp_time(ms))
    h = t // 3600000
    m = (t % 3600000) // 60000
    s = (t % 60000) // 1000
    cs = (t % 1000) // 10
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def lua_tointeger(v) -> int:
    """lua_tointeger on x64 LuaJIT: C cast, i.e. truncation toward zero."""
    return int(float(v))


# ---------------------------------------------------------------- strings

def inline_string_encode(s: str) -> str:
    out = bytearray()
    for b in s.encode("utf-8"):
        if b <= 0x1F or b in (0x23, 0x2C, 0x3A, 0x7C):
            out += f"#{b:02X}".encode("ascii")
        else:
            out.append(b)
    return out.decode("utf-8", "replace")


def inline_string_decode(s: str) -> str:
    data = s.encode("utf-8")
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        # Aegisub only decodes when two more chars follow and i + 2 < size
        if data[i] != 0x23 or i + 2 >= n:
            out.append(data[i])
            i += 1
        else:
            try:
                out.append(int(data[i + 1:i + 3].decode("ascii"), 16) & 0xFF)
            except ValueError:
                out.append(0)
            i += 3
    return out.decode("utf-8", "replace")


def uuencode(data: bytes) -> str:
    out = []
    size = len(data)
    for pos in range(0, size, 3):
        src = (data[pos:pos + 3] + b"\0\0")[:3]
        dst = [src[0] >> 2,
               ((src[0] & 0x3) << 4) | ((src[1] & 0xF0) >> 4),
               ((src[1] & 0xF) << 2) | ((src[2] & 0xC0) >> 6),
               src[2] & 0x3F]
        for i in range(min(size - pos + 1, 4)):
            out.append(chr(dst[i] + 33))
    return "".join(out)


def uudecode(text: str) -> bytes:
    data = text.encode("latin-1", "replace")
    ret = bytearray()
    n = len(data)
    pos = 0
    while pos + 1 < n:
        nbytes = 0
        src = [0, 0, 0, 0]
        i = 0
        while i < 4 and pos < n:
            c = data[pos]
            if c and c not in (10, 13):
                src[i] = (c - 33) & 0xFF
                i += 1
                nbytes += 1
            pos += 1
        if nbytes > 1:
            ret.append(((src[0] << 2) | (src[1] >> 4)) & 0xFF)
        if nbytes > 2:
            ret.append((((src[1] & 0xF) << 4) | (src[2] >> 2)) & 0xFF)
        if nbytes > 3:
            ret.append((((src[2] & 0x3) << 6) | src[3]) & 0xFF)
    return bytes(ret)


def encode_extradata_value(value: str) -> str:
    enc = inline_string_encode(value)
    raw = value.encode("utf-8")
    if 4 * len(raw) < 3 * len(enc.encode("utf-8")):
        return "u" + uuencode(raw)
    return "e" + enc


# ---------------------------------------------------------------- colors

def parse_color(text: str) -> tuple[int, int, int, int]:
    """agi::Color(string) for the formats that occur in ASS files. Returns (r, g, b, a)."""
    s = text.strip()
    if s.startswith("#"):
        h = s[1:]
        try:
            if len(h) >= 6:
                return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16) if len(h) >= 8 else 0
            if len(h) == 3:
                return int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16), 0
        except ValueError:
            return 0, 0, 0, 0
        return 0, 0, 0, 0
    if s.lower().startswith("rgb("):
        try:
            parts = [int(p) for p in s[4:].rstrip(")").split(",")]
            return parts[0], parts[1], parts[2], 0
        except (ValueError, IndexError):
            return 0, 0, 0, 0
    # ASS: &HAABBGGRR / &HBBGGRR& / plain decimal
    body = s
    if body[:2].lower() == "&h":
        body = body[2:]
        digits = ""
        for c in body:
            if c in "0123456789abcdefABCDEF":
                digits += c
            else:
                break
        v = int(digits[-8:], 16) if digits else 0
    else:
        try:
            v = int(body.rstrip("&")) & 0xFFFFFFFF
        except ValueError:
            v = 0
    return v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF, (v >> 24) & 0xFF


def format_style_color(rgba: tuple[int, int, int, int]) -> str:
    """agi::Color::GetAssStyleFormatted: &HAABBGGRR."""
    r, g, b, a = rgba
    return f"&H{a:02X}{b:02X}{g:02X}{r:02X}"


def fmt_g(v: float) -> str:
    """printf %g, used by AssStyle::UpdateData."""
    return "%g" % v
