from os import sep

from constructor.utils import make_VIProductVersion, normalize_path


def test_make_VIProductVersion():
    f = make_VIProductVersion
    assert f("3") == "3.0.0.0"
    assert f("1.5") == "1.5.0.0"
    assert f("2.71.6") == "2.71.6.0"
    assert f("5.2.10.7") == "5.2.10.7"
    assert f("5.2dev") == "5.0.0.0"
    assert f("5.26.8.9.3") == "5.26.8.9"
    assert f("x") == "0.0.0.0"


def test_normalize_path():
    path = "//test//test/test".replace("/", sep)
    assert normalize_path(path) == "/test/test/test".replace("/", sep)

    path = "test///test/test".replace("/", sep)
    assert normalize_path(path) == "test/test/test".replace("/", sep)
