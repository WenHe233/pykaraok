"""Getting a moonc that runs.  Nothing here downloads anything or needs moonc installed."""
import io
import subprocess
import sys
import urllib.request

import pytest

from pykaraok.aegi import moon
from pykaraok.cli import main


def test_a_moonc_that_runs_is_kept(monkeypatch):
    monkeypatch.setattr(moon, "find_moonc", lambda: "good")
    monkeypatch.setattr(moon, "runs", lambda exe: True)
    monkeypatch.setattr(moon, "download_moonc", lambda log=print: pytest.fail("no download needed"))
    assert moon.ensure_moonc() == "good"


@pytest.mark.parametrize("found", ["broken", None])
def test_a_moonc_that_does_not_run_is_replaced(monkeypatch, found):
    """The release used until now needs msys-2.0.dll, so it only ran from Git Bash."""
    monkeypatch.setattr(moon, "find_moonc", lambda: found)
    monkeypatch.setattr(moon, "runs", lambda exe: False)
    monkeypatch.setattr(moon, "download_moonc", lambda log=print: "downloaded")
    assert moon.ensure_moonc() == "downloaded"


def test_runs_tells_whether_a_program_starts(tmp_path):
    assert moon.runs(sys.executable.replace("python", "no_such_python")) is False
    garbage = tmp_path / ("moonc.exe" if sys.platform == "win32" else "moonc")
    garbage.write_bytes(b"this is not a program")
    garbage.chmod(0o755)
    assert moon.runs(str(garbage)) is False


def test_download_is_checked_against_its_digest(monkeypatch, tmp_path):
    if sys.platform not in moon._ASSETS:
        pytest.skip("no prebuilt moonc for this platform")
    monkeypatch.setenv("PYKARAOK_CACHE", str(tmp_path))
    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout: io.BytesIO(b"not the release"))
    with pytest.raises(moon.MoonCompileError, match="SHA-256 mismatch"):
        moon.download_moonc(log=lambda m: None)
    assert not list((tmp_path / "tools").iterdir())


def test_windows_build_does_not_need_msys():
    assert "luajit" in moon._ASSETS["win32"][0]


def test_silent_failure_says_something(monkeypatch):
    """A missing DLL ends moonc with 0xC0000135 and no output: the error message used to be empty."""
    monkeypatch.setattr(moon.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, -1073741515, b"", b""))
    with pytest.raises(moon.MoonCompileError, match="0xc0000135.*setup moonc"):
        moon.compile_text("x = 1", "x.moon", moonc="moonc")


def test_output_uses_lf(monkeypatch):
    """The Windows build writes CRLF, which would end up in vendor/ and in the cache."""
    monkeypatch.setattr(moon.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, b"local x = 1\r\nreturn x\r\n", b""))
    assert moon.compile_text("x = 1", "x.moon", moonc="moonc") == "local x = 1\nreturn x\n"


def test_doctor_reports_a_moonc_that_does_not_run(monkeypatch, capsys):
    monkeypatch.setattr(moon, "find_moonc", lambda: "broken")
    monkeypatch.setattr(moon, "runs", lambda exe: False)
    assert main(["doctor"]) == 0
    assert "moonc: broken (does not run" in capsys.readouterr().out
