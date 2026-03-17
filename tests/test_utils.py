from os import sep

from constructor.utils import (
    bat_env_var_esc,
    get_condarc_content,
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
