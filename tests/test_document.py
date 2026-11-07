"""AssDocument: lines are split like Aegisub splits them, and what is not changed is written back as it was."""
import pytest

from pykaraok.ass.document import AssDocument

STYLE = ("Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
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
