import sys

import pytest

# winexe.py needs Pillow, which isn't installed on Linux. Skip this file there
# and only import winexe inside each test, so collection doesn't fail.
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="winexe is Windows-only")


@pytest.mark.parametrize(
    "platform,expected",
    [
        ("win-32", ("32-bit", 32)),
        ("win-64", ("64-bit", 64)),
        ("win-arm64", ("ARM64", 64)),
    ],
)
def test_parse_arch(platform, expected):
    from constructor.winexe import parse_arch

    assert parse_arch(platform) == expected
