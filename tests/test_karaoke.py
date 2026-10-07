"""parse_karaoke_data cases derived from Aegisub's ParseKaraokeSyllables (src/ass_karaoke.cpp)."""
from pykaraok.aegi.karaoke import parse_blocks, parse_karaoke_data, split_override


def syls(text, start=1000):
    return parse_karaoke_data(text, start)[1:]


def test_index_zero_placeholder():
    res = parse_karaoke_data("{\\k10}a", 0)
    assert res[0] == {"duration": 0, "start_time": 0, "end_time": 0, "tag": "", "text": "", "text_stripped": ""}


def test_basic_relative_times():
    s = syls("{\\k10}a{\\k20}b")
    assert [(x["start_time"], x["end_time"], x["duration"], x["text"]) for x in s] == [
        (0, 100, 100, "a"), (100, 300, 200, "b")]


def test_tags_before_first_k_stay_with_first_syllable():
    # a zero-length, zero-duration syllable is not emitted; its tags carry over
    s = syls("{\\an8\\k10}あ{\\k20}い")
    assert s[0]["text"] == "{\\an8}あ"
    assert s[0]["text_stripped"] == "あ"
    assert len(s) == 2


def test_leading_text_becomes_its_own_syllable():
    s = syls("ab{\\k10}c")
    assert [(x["text"], x["duration"], x["tag"]) for x in s] == [("ab", 0, "\\k"), ("c", 100, "\\k")]


def test_tag_kinds():
    s = syls("{\\K10}a{\\kf20}b{\\ko30}c")
    assert [x["tag"] for x in s] == ["\\kf", "\\kf", "\\ko"]


def test_kt_matches_k_with_zero_duration():
    # Aegisub has no \kt prototype: "\kt50" is "\k" with parameter "t50" -> atoi -> 0
    s = syls("{\\k10}a{\\kt50}b")
    assert s[1]["tag"] == "\\k" and s[1]["duration"] == 0


def test_fractional_duration_truncates():
    assert syls("{\\k12.7}a")[0]["duration"] == 120


def test_comment_blocks_kept_in_text():
    s = syls("{\\k10}a{note}b")
    assert s[0]["text"] == "a{note}b"
    assert s[0]["text_stripped"] == "ab"


def test_override_after_k_in_same_block():
    s = syls("{\\k10\\1c&HFF&}a")
    assert s[0]["text"] == "{\\1c&HFF&}a"


def test_paren_aware_split():
    assert split_override("\\t(0,100,\\fs20)\\k10") == ["\\t(0,100,\\fs20)", "\\k10"]


def test_drawing_blocks_are_not_text():
    blocks = parse_blocks("{\\p1}m 0 0 l 1 1{\\p0}x")
    assert ("drawing", "m 0 0 l 1 1") in blocks
    s = syls("{\\k10\\p1}m 0 0 l 1 1{\\p0}x")
    assert s[0]["text_stripped"] == "x"


def test_multibyte_override_offsets():
    s = syls("{\\k10}あ{\\i1}い")
    assert s[0]["text"] == "あ{\\i1}い"
