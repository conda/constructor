from os import environ, sep

import pytest

from constructor.utils import (
    bat_echo_esc,
    bat_env_var_esc,
    env_vars,
    get_condarc_content,
    hash_files,
    make_VIProductVersion,
    normalize_path,
)


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


def test_bat_env_var_esc():
    """Test escaping strings for Windows batch file SET commands."""
    # Plain strings pass through unchanged
    assert bat_env_var_esc("foo") == "foo"
    assert bat_env_var_esc("foo bar") == "foo bar"

    # Single quotes are allowed (literal in batch)
    assert bat_env_var_esc("foo 'bar'") == "foo 'bar'"

    # Special characters are escaped
    assert bat_env_var_esc("50%") == "50%%"
    assert bat_env_var_esc("a & b") == "a ^& b"
    assert bat_env_var_esc("a | b") == "a ^| b"
    assert bat_env_var_esc("a < b > c") == "a ^< b ^> c"
    assert bat_env_var_esc("a^b") == "a^^b"
    assert bat_env_var_esc("foo!") == "foo^!"

    # Combined special characters
    assert bat_env_var_esc("100% & done!") == "100%% ^& done^!"


def test_bat_echo_esc():
    """Test escaping strings for Windows batch file ECHO commands."""
    # Plain strings pass through unchanged
    assert bat_echo_esc("foo") == "foo"
    assert bat_echo_esc("foo bar") == "foo bar"

    # Special characters are escaped
    assert bat_echo_esc("a & b") == "a ^& b"
    assert bat_echo_esc("a | b") == "a ^| b"
    assert bat_echo_esc("a < b > c") == "a ^< b ^> c"
    assert bat_echo_esc("a^b") == "a^^b"

    # Percent and exclamation are NOT escaped (unlike bat_env_var_esc)
    assert bat_echo_esc("50%") == "50%"
    assert bat_echo_esc("foo!") == "foo!"

    # Virtual specs examples
    assert bat_echo_esc("__win<0") == "__win^<0"
    assert bat_echo_esc("__cuda>=11") == "__cuda^>=11"
    assert bat_echo_esc("__win<0 __cuda>=11") == "__win^<0 __cuda^>=11"


def test_get_condarc_content_with_write_condarc():
    """Test that get_condarc_content returns YAML content when write_condarc is True."""
    info = {
        "write_condarc": True,
        "channels": ["conda-forge", "defaults"],
    }
    content = get_condarc_content(info)
    assert content is not None
    assert "channels:" in content
    assert "conda-forge" in content
    assert "defaults" in content


def test_get_condarc_content_with_condarc_dict():
    """Test that get_condarc_content returns YAML content when condarc is a dict."""
    info = {
        "condarc": {
            "channels": ["my-channel"],
            "ssl_verify": False,
        },
    }
    content = get_condarc_content(info)
    assert content is not None
    assert "channels:" in content
    assert "my-channel" in content
    assert "ssl_verify:" in content


def test_get_condarc_content_returns_none():
    """Test that get_condarc_content returns None when no condarc settings are provided."""
    info = {}
    assert get_condarc_content(info) is None

    # write_condarc without channels should also return None
    info = {"write_condarc": True}
    assert get_condarc_content(info) is None


def test_invalid_algorithm(tmp_path):
    """Test that hash_files raises a ValueError for invalid algorithm names."""

    path = tmp_path / "test.txt"
    path.write_text("test string")
    with pytest.raises(ValueError, match="bad_algorithm"):
        hash_files([path], "bad_algorithm")


VAR = "CONSTRUCTOR_TEST_ENV_VAR"


def test_env_vars_sets_and_restores(monkeypatch):
    """The variables are set inside the block and unset after it, and the callback sees both."""
    monkeypatch.delenv(VAR, raising=False)
    calls = []

    def callback():
        calls.append(environ.get(VAR))

    with env_vars({VAR: "inner"}, callback):
        assert environ[VAR] == "inner"
        calls.append("inside")

    assert VAR not in environ
    assert calls == ["inner", "inside", None]


def test_env_vars_restores_previous_value(monkeypatch):
    """A variable that was already set keeps its old value once the block exits."""
    monkeypatch.setenv(VAR, "outer")

    with env_vars({VAR: "inner"}):
        assert environ[VAR] == "inner"

    assert environ[VAR] == "outer"


def test_env_vars_restores_after_an_exception(monkeypatch):
    """A failing block still restores the previous values and calls the callback on exit."""
    monkeypatch.setenv(VAR, "outer")
    calls = []

    with pytest.raises(RuntimeError):
        with env_vars({VAR: "inner"}, lambda: calls.append(environ.get(VAR))):
            raise RuntimeError("boom")

    assert environ[VAR] == "outer"
    assert calls == ["inner", "outer"]
