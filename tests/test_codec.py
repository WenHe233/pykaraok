from pykaraok.ass import codec


def test_time_parse_and_format():
    assert codec.parse_time("0:01:02.34") == 62340
    assert codec.parse_time("1:00:00.5") == 3600500
    assert codec.parse_time("0:00:01.234") == 1234
    assert codec.format_time(62340) == "0:01:02.34"


def test_time_rounding_matches_aegisub():
    # agi::Time::operator int: (t + 5) - (t + 5) % 10
    assert codec.format_time(1004) == "0:00:01.00"
    assert codec.format_time(1005) == "0:00:01.01"
    assert codec.format_time(1009) == "0:00:01.01"


def test_time_clamp():
    assert codec.format_time(-50) == "0:00:00.00"
    assert codec.format_time(10 ** 9) == "9:59:59.99"


def test_colors():
    assert codec.parse_color("&H00FFFFFF") == (255, 255, 255, 0)
    assert codec.parse_color("&H80112233&") == (0x33, 0x22, 0x11, 0x80)
    assert codec.parse_color("&H0000FF&") == (255, 0, 0, 0)
    assert codec.format_style_color((0x33, 0x22, 0x11, 0x80)) == "&H80112233"


def test_inline_string_codec():
    s = "a,b:c|d#e\n"
    enc = codec.inline_string_encode(s)
    assert enc == "a#2Cb#3Ac#7Cd#23e#0A"[:-3] + "#0A"
    # Aegisub's decoder skips a trailing #XX (i + 2 >= size), so round-trip a padded value
    assert codec.inline_string_decode(codec.inline_string_encode("x,y") + "z") == "x,yz"


def test_uuencode_roundtrip():
    data = bytes(range(40))
    assert codec.uudecode(codec.uuencode(data)) == data
