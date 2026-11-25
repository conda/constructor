from os import environ
from pathlib import Path
from types import SimpleNamespace

import pytest
from conda.models.version import VersionOrder

from constructor.utils import (
    StandaloneExeType,
    bat_echo_esc,
    bat_env_var_esc,
    env_vars,
    explained_check_call,
    get_condarc_content,
    hash_files,
    identify_conda_exe,
    make_VIProductVersion,
    shortcuts_flags,
    win_str_esc,
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


def _mock_identify_commands(mocker, version_output, help_output=""):
    def fake_check_output(cmd, **_kwargs):
        if cmd[1] == "--version":
            return version_output
        if cmd[1] == "--help":
            return help_output
        raise AssertionError(f"unexpected command: {cmd}")

    return mocker.patch("constructor.utils.check_output", side_effect=fake_check_output)


@pytest.mark.parametrize(
    (
        "platform",
        "version_output",
        "help_output",
        "expected_type",
        "expected_version",
        "expected_target_name",
    ),
    [
        pytest.param(
            "linux",
            "conda 24.11.0",
            "",
            StandaloneExeType.CONDA,
            "24.11.0",
            "_conda",
            id="conda-standalone",
        ),
        pytest.param(
            "linux",
            "conda 26.10.0",
            "",
            StandaloneExeType.CONDA,
            "26.10.0",
            "_conda",
            id="conda-standalone-newer",
        ),
        pytest.param(
            "linux",
            "1.5.10",
            "micromamba: help",
            StandaloneExeType.MAMBA,
            "1.5.10",
            "micromamba",
            id="micromamba-below-conda-minimum",
        ),
        pytest.param(
            "win32",
            "2.0.0",
            "micromamba: help",
            StandaloneExeType.MAMBA,
            "2.0.0",
            "micromamba.exe",
            id="micromamba-windows",
        ),
        pytest.param(
            "linux",
            "unidentified 1.0",
            "not a known binary",
            None,
            None,
            "conda.exe",
            id="unidentified-binary",
        ),
    ],
)
def test_identify_conda_exe(
    tmp_path,
    mocker,
    platform,
    version_output,
    help_output,
    expected_type,
    expected_version,
    expected_target_name,
):
    exe = tmp_path / "conda.exe"
    exe.write_bytes(b"standalone")
    mocker.patch("constructor.utils.sys.platform", platform)
    _mock_identify_commands(mocker, version_output, help_output)
    # Non-Windows binaries and micromamba never need the capability probes.
    mocker.patch(
        "constructor.utils.subprocess.run",
        side_effect=AssertionError("unexpected capability probe"),
    )

    data = identify_conda_exe(exe)

    assert data["path"] == exe
    assert data.get("type") == expected_type
    assert data.get("version") == (VersionOrder(expected_version) if expected_version else None)
    assert data["target_name"] == expected_target_name
    assert data["supports_logging"] is False
    assert "has_windows_subcommand" not in data


@pytest.mark.parametrize(
    ("version_output", "error"),
    [
        pytest.param("conda 24.10.9", True, id="below-minimum"),
        pytest.param("conda 24.11.0", False, id="at-minimum"),
        pytest.param("conda 26.10.0", False, id="above-minimum"),
    ],
)
def test_identify_conda_exe_enforces_minimum_version(tmp_path, mocker, version_output, error):
    exe = tmp_path / "conda.exe"
    exe.write_bytes(b"standalone")
    mocker.patch("constructor.utils.sys.platform", "linux")
    _mock_identify_commands(mocker, version_output)

    if error:
        with pytest.raises(RuntimeError, match="at least 24.11.0"):
            identify_conda_exe(exe)
    else:
        data = identify_conda_exe(exe)
        assert data["version"] == VersionOrder(version_output.split()[1])


@pytest.mark.parametrize(
    ("log_written", "returncode", "expected_logging", "expected_subcommand"),
    [
        pytest.param(True, 0, True, True, id="logging-and-subcommand"),
        pytest.param(False, 2, False, False, id="no-logging-no-subcommand"),
    ],
)
def test_identify_conda_exe_windows_capabilities(
    tmp_path, mocker, log_written, returncode, expected_logging, expected_subcommand
):
    exe = tmp_path / "conda.exe"
    exe.write_bytes(b"standalone")
    mocker.patch("constructor.utils.sys.platform", "win32")
    _mock_identify_commands(mocker, "conda 26.10.0")

    def fake_run(cmd, **_kwargs):
        for arg in cmd:
            if str(arg).startswith("--log-file="):
                if log_written:
                    Path(str(arg).split("=", 1)[1]).touch()
                return SimpleNamespace(returncode=0)
        return SimpleNamespace(returncode=returncode)

    mocker.patch("constructor.utils.subprocess.run", side_effect=fake_run)

    data = identify_conda_exe(exe)

    assert data["target_name"] == "_conda.exe"
    assert data["supports_logging"] is expected_logging
    assert data["has_windows_subcommand"] is expected_subcommand


def test_win_str_esc_accepts_paths():
    assert (
        win_str_esc(Path("C:/Program Files/constructor.exe"))
        == '"C:/Program Files/constructor.exe"'
    )


def test_explained_check_call_logs_path_arguments(mocker):
    check_call = mocker.patch("constructor.utils.check_call")
    mocker.patch("constructor.utils.logger.debug")

    explained_check_call(["productbuild", Path("installer.pkg")])

    check_call.assert_called_once_with(["productbuild", Path("installer.pkg")])


def test_identify_conda_exe_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="does not exist"):
        identify_conda_exe(tmp_path / "conda.exe")


@pytest.mark.parametrize(
    ("menu_packages", "exe_type", "expected"),
    [
        pytest.param(None, StandaloneExeType.CONDA, "", id="unset-conda"),
        pytest.param(None, StandaloneExeType.MAMBA, "", id="unset-micromamba"),
        pytest.param(
            ["console_shortcut"],
            StandaloneExeType.CONDA,
            "--shortcuts-only=console_shortcut",
            id="conda-subset",
        ),
        pytest.param(
            ["console_shortcut", "other"],
            StandaloneExeType.CONDA,
            "--shortcuts-only=console_shortcut --shortcuts-only=other",
            id="conda-subset-multiple",
        ),
        pytest.param(
            ["console_shortcut"],
            StandaloneExeType.MAMBA,
            "",
            id="micromamba-unsupported-subset",
        ),
        pytest.param([], StandaloneExeType.CONDA, "--no-shortcuts", id="empty-conda"),
        pytest.param([], StandaloneExeType.MAMBA, "--no-shortcuts", id="empty-micromamba"),
    ],
)
def test_shortcuts_flags(menu_packages, exe_type, expected):
    info = {} if menu_packages is None else {"menu_packages": menu_packages}
    assert shortcuts_flags(info, exe_type) == expected


def test_shortcuts_flags_falls_back_to_info_type():
    info = {
        "_conda_exe": {"type": StandaloneExeType.MAMBA},
        "menu_packages": ["console_shortcut"],
    }
    assert shortcuts_flags(info) == ""
