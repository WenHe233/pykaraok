"""The command line: failures come out as `error: ...`, or as JSON with --json, never as a traceback."""
import json
import shutil
import sys

import pytest

from pykaraok.cli import main
from pykaraok.cli_tools import _is_junction, _link_dir
from test_fonts import make_font

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

MINIMAL = "[Script Info]\nScriptType: v4.00+\n"

# name: (arguments, what the message must say)
FAILURES = {
    "missing video": (["render", "frame", "{ass}", "--video", "{tmp}/nope.mkv", "--at", "1", "-o", "{tmp}/x.png"], "ffprobe failed"),
    "missing audio": (["beats", "{tmp}/nope.wav", "--from", "0", "--to", "10"], "ffmpeg failed"),
    "missing output folder": (["render", "frame", "{ass}", "--no-video", "--at", "1", "-o", "{tmp}/no/dir/x.png"], "ffmpeg failed"),
    "steady without original": (["check", "{ass}", "--steady", "--no-video"], "--steady needs --original"),
    "no time range": (["render", "sheet", "{tmp}/minimal.ass", "--no-video"], "--from and --to"),
    "unknown phase": (["render", "lines", "{ass}", "--no-video", "--phases", "in,zzz"], "unknown phase zzz (choose from in, in+"),
    "bad part": (["draw", "compose", "--font", "{tmp}/f.ttf", "--size", "50", "--part", "xx!!"], "bad --part"),
    "glyph missing": (["draw", "text", "B", "--font", "{tmp}/f.ttf", "--size", "50"], "has no glyph for 'B'"),
    "traditional onto itself": (["cht", "{ass}", "-o", "{ass}", "--styles", "Default"], "new file"),
    "not a zip": (["fonts", "unpack", "{tmp}/bad.zip"], "not a zip file"),
    "missing input": (["apply", "{tmp}/nope.ass", "-o", "{tmp}/x.ass"], "nope.ass"),
}


@pytest.fixture
def argv(tmp_path, data_dir, monkeypatch):
    monkeypatch.setenv("PYKARAOK_CACHE", str(tmp_path / "cache"))
    (tmp_path / "minimal.ass").write_text(MINIMAL, encoding="utf-8")
    (tmp_path / "bad.zip").write_bytes(b"not a zip")
    make_font(tmp_path / "f.ttf", "PykCli")

    def fill(args):
        return [a.format(ass=data_dir / "basic.ass", tmp=tmp_path) for a in args]
    return fill


@needs_ffmpeg
@pytest.mark.parametrize("name", FAILURES)
def test_failure_is_reported_not_raised(name, argv, capsys):
    args, says = FAILURES[name]
    assert main(argv(args)) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert says in captured.err and "error: " in captured.err and "Traceback" not in captured.err

    assert main(argv(args) + ["--json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert says in data["error"] and data["type"]


def test_debug_variable_keeps_the_traceback(argv, monkeypatch):
    monkeypatch.setenv("PYKARAOK_DEBUG", "1")
    with pytest.raises(ValueError):
        main(argv(["draw", "compose", "--font", "{tmp}/f.ttf", "--size", "50", "--part", "xx!!"]))


def test_a_missing_optional_module_is_reported(argv, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "pykaraok.text.cht", None)
    assert main(argv(["cht", "{ass}", "-o", "{tmp}/out.ass", "--styles", "Default"])) == 1
    assert "error: " in capsys.readouterr().err


def test_draw_compose_says_what_to_install(argv, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "pykaraok.draw.compose", None)
    assert main(argv(["draw", "compose", "--font", "{tmp}/f.ttf", "--size", "50", "--part", "A"])) == 1
    assert "pip install skia-pathops" in capsys.readouterr().err


def test_skill_link_can_be_replaced(tmp_path):
    """Installing again failed on Python 3.11 (Path.is_junction is 3.12), and on every version
    after the repository moved, which is when it has to be done again."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "SKILL.md").write_text("x", encoding="utf-8")
    dst = tmp_path / "skills" / "pykaraok"
    _link_dir(src, dst, False)
    _link_dir(src, dst, False)
    assert (dst / "SKILL.md").exists() and (src / "SKILL.md").exists()

    moved = src.rename(tmp_path / "moved")
    assert not dst.exists()
    _link_dir(moved, dst, False)
    assert (dst / "SKILL.md").exists()

    # a copy over a link leaves the source alone, and a link replaces a copy
    assert _link_dir(moved, dst, True) == "copied"
    assert (moved / "SKILL.md").exists() and not (dst.is_symlink() or _is_junction(dst))
    _link_dir(moved, dst, False)
    assert dst.is_symlink() or _is_junction(dst)
