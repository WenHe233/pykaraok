import os
from pathlib import Path

import pytest

HERE = Path(__file__).parent
DATA = HERE / "data"

# Folders of earlier projects used as regression material.  Point
# PYKARAOK_PROJECTS at the directory that contains them.
PROJECTS = Path(os.environ.get("PYKARAOK_PROJECTS", r"C:\Users\Administrator\Desktop\github"))


@pytest.fixture
def data_dir():
    return DATA


@pytest.fixture
def projects():
    return PROJECTS


def windows_font_dir() -> Path:
    return Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
