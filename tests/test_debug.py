from contextlib import contextmanager
from pathlib import Path
from subprocess import check_call
from tempfile import TemporaryDirectory
import os
import json

here = Path(__file__).parent
examples = here / ".." / "examples"


@contextmanager
def working_directory(path):
    wd = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(wd)


def test_debug_licenses():
    with TemporaryDirectory() as tmp:
        with working_directory(tmp):
            check_call(["constructor", str(examples / "noconda"), "--debug"])
            with open("info.json") as f:
                data = json.load(f)
                assert "_licenses" in data
