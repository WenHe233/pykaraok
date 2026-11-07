"""A fresh clone must hold everything the package needs.

src/pykaraok/build/ was once caught by the build/ rule in .gitignore: it worked in the
checkout it was written in and was missing from every clone.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_no_project_file_is_git_ignored():
    if not shutil.which("git") or not (ROOT / ".git").exists():
        pytest.skip("needs a git checkout")
    out = subprocess.run(["git", "ls-files", "--others", "--ignored", "--exclude-standard", "--",
                          "src", "tests", "tools", "skill", "examples"],
                         cwd=ROOT, capture_output=True, encoding="utf-8", check=True).stdout
    ignored = [p for p in out.splitlines() if "__pycache__" not in p and ".egg-info" not in p]
    assert ignored == []
