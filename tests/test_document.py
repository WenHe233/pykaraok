"""AssDocument: lines are split like Aegisub splits them, and what is not changed is written back as it was."""
import pytest

from pykaraok.ass.document import AssDocument, parse_event, parse_style

STYLE =("Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
         "0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1")
INFO = "[Script Info]\nScriptType: v4.00+\nPlayResX: 640\nPlayResY: 360\n"
STYLES = ("[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
          "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, "
          "Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n" + STYLE + "\n")
EVENTS = "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
EVENT = "Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,x\n"
FILE = INFO + "\n" + STYLES + "\n" + EVENTS + EVENT


@pytest.mark.parametrize("ch", [" ", " ", "\x85", "\x0c", "\x0b", "\x1c", "\x1d", "\x1e"],
                         ids=["LS", "PS", "NEL", "FF", "VT", "FS", "GS", "RS"])
def test_only_lf_ends_a_line(ch):
    """str.splitlines() breaks at all of these: everything after them used to be lost."""
    text = FILE.replace(",,x\n", f",,AB{ch}CD\n")
    doc = AssDocument.from_text(text)
    assert [e["text"] for e in doc.events] == [f"AB{ch}CD"]
    assert doc.to_text() == text


def test_cr_before_lf_is_the_newline():
    text = FILE.replace("\n", "\r\n")
    doc = AssDocument.from_text(text)
    assert doc.newline == "\r\n"
    assert [e["text"] for e in doc.events] == ["x"]
    assert doc.to_text() == text


def test_no_newline_at_the_end():
    text = FILE.rstrip("\n")
    assert AssDocument.from_text(text).to_text() == text


@pytest.mark.parametrize("text", [
    INFO + "\n\n" + STYLES + "\n\n\n" + EVENTS + EVENT,
    INFO + STYLES + EVENTS + EVENT,
    FILE + "\n",
    FILE + "\n\n",
    INFO + "\n" + STYLES.replace("Style:", "; a style comment\nStyle:") + "\n" + EVENTS + "; a note\n" + EVENT + "; another\n",
    INFO + "\n" + STYLES + "\n[Fonts]\nfontname: a.ttf\n\n\n" + EVENTS + EVENT + "\n[Aegisub Extra]\nx\n\n\ny\n",
    INFO + "\n[V4+ Styles]\n" + STYLE + "\n\n[Events]\n" + EVENT,
], ids=["extra blank lines", "no blank lines", "blank line at the end", "two blank lines at the end",
        "comments in sections", "other sections", "no Format lines"])
def test_unchanged_file_is_written_back_byte_for_byte(text):
    assert AssDocument.from_text(text).to_text() == text
    crlf = b"\xef\xbb\xbf" + text.replace("\n", "\r\n").encode("utf-8")
    assert AssDocument.from_bytes(crlf).to_bytes() == crlf


def test_changed_entries_leave_the_other_lines_in_place():
    new = "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,new\n"
    text = (INFO + "\n\n" + STYLES + "\n" + EVENTS + "; a note\n" + EVENT + "; another\n\n"
            "[Aegisub Project Garbage]\nVideo File: v.mkv\n")
    doc = AssDocument.from_text(text)
    doc.events.append(parse_event(new.strip()))
    assert doc.to_text() == text.replace(EVENT, EVENT + new)
    doc.events = []
    assert doc.to_text() == text.replace(EVENT, "")


def test_changed_script_info_keeps_comments_and_project_properties():
    text = ("[Script Info]\n; comment\nTitle: a\nCollisions: Normal\nVideo File: v.mkv\n"
            "Aegisub Video Position: 12\nScriptType: v4.00+\n\n" + STYLES + "\n" + EVENTS + EVENT)
    doc = AssDocument.from_text(text)
    assert [i["key"] for i in doc.info] == ["Title", "ScriptType"]
    doc.info[0]["value"] = "b"
    assert doc.to_text() == text.replace("Title: a", "Title: b")
    doc.info.append({"class": "info", "section": "[Script Info]", "key": "PlayResX", "value": "640"})
    assert doc.to_text() == text.replace("Title: a", "Title: b").replace("v4.00+\n", "v4.00+\nPlayResX: 640\n")


def test_entries_of_a_file_without_their_section_are_written():
    # a style added by --@style to a lyrics file that has no style section
    doc = AssDocument.from_text(INFO + "\n" + EVENTS + EVENT)
    doc.styles.append(parse_style(STYLE))
    assert doc.to_text() == FILE
    # both missing, and the last section does not end with a blank line
    doc = AssDocument.from_text(INFO)
    doc.styles.append(parse_style(STYLE))
    doc.events.append(parse_event(EVENT.strip()))
    assert doc.to_text() == FILE
    # the sections go before the extradata
    doc = AssDocument.from_text(INFO + "\n[Aegisub Extradata]\nData: 0,a,eb\n")
    doc.events.append(dict(parse_event(EVENT.strip()), extra_ids=[0]))
    reread = AssDocument.from_text(doc.to_text())
    assert [s.key for s in reread.sections] == ["script info", "events", "aegisub extradata"]
    assert reread.extra_for(reread.events[0]["extra_ids"]) == {"a": "b"}


def test_two_sections_of_one_kind_do_not_double_the_entries():
    text = INFO + "\n" + STYLES + "\n" + EVENTS + EVENT + "\n" + EVENTS + EVENT.replace(",,x", ",,y")
    assert [e["text"] for e in AssDocument.from_text(AssDocument.from_text(text).to_text()).events] == ["x", "y"]


def test_extradata_no_line_uses_is_dropped_like_aegisub():
    """AssFile::CleanExtradata, which SubsController::Save calls."""
    text = FILE.replace(",,x", ",,{=1}x") + "\n[Aegisub Extradata]\nData: 0,a,eb\nData: 1,c,ed\n"
    assert AssDocument.from_text(text).to_text() == text.replace("Data: 0,a,eb\n", "")
