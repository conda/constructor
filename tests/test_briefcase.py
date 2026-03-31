import sys
import tarfile
from pathlib import Path

import pytest

from constructor.briefcase import (
    Payload,
    _get_python_info,
    _get_script_env_variables,
    _setup_envs_commands,
    create_uninstall_options_list,
    get_bundle_app_name,
    get_name_version,
)
from constructor.conda_interface import cc_platform

"""
    Here 'mock_info' is simply a 'mock' of the regular 'info' object that is used to create installers.
    It contains bare minimum in order to allow simple unit testing.
"""
mock_info = {
    "name": "MockInfo",
    "version": "1.0.0",
    "_conda_exe": str(Path(sys.prefix) / "standalone_conda" / "conda.exe"),
    "_download_dir": "",
    "_dists": [],
    "_platform": cc_platform,
    "_urls": [],
}


@pytest.mark.parametrize(
    "name_in, version_in, name_expected, version_expected",
    [
        # Valid versions
        ("Miniconda", "1", "Miniconda", "1"),
        ("Miniconda", "1.2", "Miniconda", "1.2"),
        ("Miniconda", "1.2.3", "Miniconda", "1.2.3"),
        ("Miniconda", "1.2a1", "Miniconda", "1.2a1"),
        ("Miniconda", "1.2b2", "Miniconda", "1.2b2"),
        ("Miniconda", "1.2rc3", "Miniconda", "1.2rc3"),
        ("Miniconda", "1.2.post4", "Miniconda", "1.2.post4"),
        ("Miniconda", "1.2.dev5", "Miniconda", "1.2.dev5"),
        ("Miniconda", "1.2rc3.post4.dev5", "Miniconda", "1.2rc3.post4.dev5"),
        # Hyphens are treated as dots
        ("Miniconda", "1.2-3", "Miniconda", "1.2.3"),
        ("Miniconda", "1.2-3.4-5.6", "Miniconda", "1.2.3.4.5.6"),
        # Additional text before and after the last valid version should be treated as
        # part of the name.
        ("Miniconda", "1.2 3.4 5.6", "Miniconda 1.2 3.4", "5.6"),
        ("Miniconda", "1.2_3.4_5.6", "Miniconda 1.2_3.4", "5.6"),
        ("Miniconda", "1.2c3", "Miniconda 1.2c", "3"),
        ("Miniconda", "1.2rc3.dev5.post4", "Miniconda 1.2rc3.dev5.post", "4"),
        ("Miniconda", "py313", "Miniconda py", "313"),
        ("Miniconda", "py.313", "Miniconda py", "313"),
        ("Miniconda", "py3.13", "Miniconda py", "3.13"),
        ("Miniconda", "py313_1.2", "Miniconda py313", "1.2"),
        ("Miniconda", "1.2 and more", "Miniconda and more", "1.2"),
        ("Miniconda", "1.2! and more", "Miniconda ! and more", "1.2"),
        ("Miniconda", "py313 1.2 and more", "Miniconda py313 and more", "1.2"),
        # Numbers in the name are not added to the version.
        ("Miniconda3", "1", "Miniconda3", "1"),
    ],
)
def test_name_version(name_in, version_in, name_expected, version_expected):
    name_actual, version_actual = get_name_version(
        {"name": name_in, "version": version_in},
    )
    assert (name_actual, version_actual) == (name_expected, version_expected)


@pytest.mark.parametrize(
    "info",
    [
        {},
        {"name": ""},
    ],
)
def test_name_empty(info):
    with pytest.raises(ValueError, match="Name is empty"):
        get_name_version(info)


@pytest.mark.parametrize(
    "info",
    [
        {"name": "Miniconda"},
        {"name": "Miniconda", "version": ""},
    ],
)
def test_version_empty(info):
    with pytest.raises(ValueError, match="Version is empty"):
        get_name_version(info)


@pytest.mark.parametrize("version_in", ["x", ".", " ", "hello"])
def test_version_invalid(version_in, caplog):
    name_actual, version_actual = get_name_version(
        {"name": "Miniconda3", "version": version_in},
    )
    assert name_actual == f"Miniconda3 {version_in}"
    assert version_actual == "0.0.1"
    assert caplog.messages == [
        f"Version {version_in!r} contains no valid version numbers; defaulting to 0.0.1"
    ]


@pytest.mark.parametrize(
    "rdi, name, bundle_expected, app_name_expected",
    [
        # Valid rdi
        ("org.conda", "ignored", "org", "conda"),
        ("org.Conda", "ignored", "org", "Conda"),
        ("org.conda-miniconda", "ignored", "org", "conda-miniconda"),
        ("org.conda_miniconda", "ignored", "org", "conda_miniconda"),
        ("org-conda.miniconda", "ignored", "org-conda", "miniconda"),
        ("org.conda.miniconda", "ignored", "org.conda", "miniconda"),
        ("org.conda.1", "ignored", "org.conda", "1"),
        # Invalid rdi
        ("org.hello-", "Miniconda", "org", "hello"),
        ("org.-hello", "Miniconda", "org", "hello"),
        ("org.hello world", "Miniconda", "org", "hello-world"),
        ("org.hello!world", "Miniconda", "org", "hello-world"),
        # Missing rdi
        (None, "x", "io.continuum", "x"),
        (None, "X", "io.continuum", "x"),
        (None, "1", "io.continuum", "1"),
        (None, "Miniconda", "io.continuum", "miniconda"),
        (None, "Miniconda3", "io.continuum", "miniconda3"),
        (None, "Miniconda3 py313", "io.continuum", "miniconda3-py313"),
        (None, "Hello, world!", "io.continuum", "hello-world"),
    ],
)
def test_bundle_app_name(rdi, name, bundle_expected, app_name_expected):
    bundle_actual, app_name_actual = get_bundle_app_name({"reverse_domain_identifier": rdi}, name)
    assert (bundle_actual, app_name_actual) == (bundle_expected, app_name_expected)


@pytest.mark.parametrize("rdi", ["", "org"])
def test_rdi_no_dots(rdi):
    with pytest.raises(ValueError, match=f"reverse_domain_identifier '{rdi}' contains no dots"):
        get_bundle_app_name({"reverse_domain_identifier": rdi}, "ignored")


@pytest.mark.parametrize("rdi", ["org.", "org.hello.", "org.hello.-"])
def test_rdi_invalid_package(rdi):
    with pytest.raises(
        ValueError,
        match=(
            f"Last component of reverse_domain_identifier '{rdi}' "
            f"contains no alphanumeric characters"
        ),
    ):
        get_bundle_app_name({"reverse_domain_identifier": rdi}, "ignored")


@pytest.mark.parametrize("name", ["", " ", "!", "-", "---"])
def test_name_no_alphanumeric(name):
    with pytest.raises(ValueError, match=f"Name '{name}' contains no alphanumeric characters"):
        get_bundle_app_name({}, name)


@pytest.mark.parametrize(
    "dists, has_python_expected, pyver_expected",
    [
        # Python present
        (["python-3.11.5-0.tar.bz2"], True, ["3", "11", "5"]),
        (["python-3.9.7-0.tar.bz2"], True, ["3", "9", "7"]),
        # Python present alongside other dists
        (["numpy-1.24.0-py311_0.tar.bz2", "python-3.11.5-0.tar.bz2"], True, ["3", "11", "5"]),
        # No python dist
        (["numpy-1.24.0-py311_0.tar.bz2"], False, []),
        # Empty dists
        ([], False, []),
    ],
)
def test_get_python_info(dists, has_python_expected, pyver_expected):
    info = {"_dists": dists}
    has_python, pyver_components = _get_python_info(info)
    assert has_python == has_python_expected
    assert pyver_components == pyver_expected


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_prepare_payload():
    """Test preparing the payload."""
    info = mock_info.copy()
    payload = Payload(info)
    payload.prepare()
    assert payload.root.is_dir()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_payload_layout():
    """Test the layout of the payload and verify that archiving
    parts of the payload works as expected.
    """
    info = mock_info.copy()
    payload = Payload(info)
    payload.prepare()

    external_dir = payload.root / "external"
    assert external_dir.is_dir()

    base_dir = payload.root / "external" / "base"
    pkgs_dir = payload.root / "external" / "base" / "pkgs"
    archive_path = external_dir / payload.archive_name
    # Since archiving removes the directory 'base_dir' and its contents
    assert not base_dir.exists()
    assert not pkgs_dir.exists()
    assert archive_path.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_payload_archive(tmp_path: Path):
    """Test that the payload archive function works as expected."""
    info = mock_info.copy()
    payload = Payload(info)

    foo_dir = tmp_path / "foo"
    foo_dir.mkdir()

    expected_text = "some test text"
    hello_file = foo_dir / "hello.txt"
    hello_file.write_text(expected_text, encoding="utf-8")

    archive_path = payload.make_archive(foo_dir, tmp_path)

    with tarfile.open(archive_path, mode="r:gz") as tar:
        member = tar.getmember("foo/hello.txt")
        f = tar.extractfile(member)
        assert f is not None
        assert f.read().decode("utf-8") == expected_text


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_payload_remove():
    """Test removing the payload."""
    info = mock_info.copy()
    payload = Payload(info)
    payload.prepare()
    root = payload.root

    assert root.is_dir()
    payload.remove()
    assert not root.is_dir()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_payload_pyproject_toml():
    """Test that the pyproject.toml file is created when the payload is prepared."""
    info = mock_info.copy()
    payload = Payload(info)
    payload.prepare()
    pyproject_toml = payload.root / "pyproject.toml"
    assert pyproject_toml.is_file()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_payload_conda_exe():
    """Test that conda-standalone is prepared."""
    info = mock_info.copy()
    payload = Payload(info)
    payload.prepare()
    external_dir = payload.root / "external"
    conda_exe = external_dir / "_conda.exe"
    assert conda_exe.is_file()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
@pytest.mark.parametrize("debug_logging", [True, False])
def test_payload_templates_are_rendered(debug_logging):
    """Test that templates are rendered when the payload is prepared."""
    info = mock_info.copy()
    payload = Payload(info)
    payload.add_debug_logging = debug_logging
    rendered_templates = payload.render_templates()
    assert len(rendered_templates) == 2  # There should be at least two files
    for f in rendered_templates:
        assert f.is_file()
        text = f.read_text(encoding="utf-8")
        assert "{{" not in text and "}}" not in text
        assert "{%" not in text and "%}" not in text
        assert "{#" not in text and "#}" not in text


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
@pytest.mark.parametrize("debug_logging", [True, False])
def test_templates_debug_mode(debug_logging):
    """Test that debug logging affects template generation."""
    info = mock_info.copy()
    payload = Payload(info)
    payload.add_debug_logging = debug_logging
    rendered_templates = payload.render_templates()
    assert len(rendered_templates) == 2

    for f in rendered_templates:
        assert f.is_file()
        with open(f) as open_file:
            lines = open_file.readlines()
        expected = "@echo on\n" if debug_logging else "@echo off\n"
        assert lines[0] == expected


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_render_templates_no_python():
    """Test when no Python dist is present, has_python is False and the
    OPTION_REGISTER_PYTHON block should not appear in the rendered output."""
    info = mock_info.copy()
    info["_dists"] = []
    payload = Payload(info)
    rendered_templates = payload.render_templates()

    run_installation = next(f for f in rendered_templates if f.name == "run_installation.bat")
    text = run_installation.read_text(encoding="utf-8")
    assert "OPTION_REGISTER_PYTHON" not in text
    assert "PythonCore" not in text


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_render_templates_with_python():
    """Test when a Python dist is present, has_python is True and the
    OPTION_REGISTER_PYTHON block should appear in the rendered output."""
    info = mock_info.copy()
    info["_dists"] = ["python-3.11.5-0.tar.bz2"]
    payload = Payload(info)
    rendered_templates = payload.render_templates()

    run_installation = next(f for f in rendered_templates if f.name == "run_installation.bat")
    text = run_installation.read_text(encoding="utf-8")
    assert "OPTION_REGISTER_PYTHON" in text
    assert "PythonCore" in text
    assert "3.11" in text


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
@pytest.mark.parametrize(
    "initialize_conda, expected_flag",
    [
        ("condabin", "--condabin"),
        ("classic", "--classic"),
    ],
)
def test_render_templates_add_to_path_flags(initialize_conda, expected_flag):
    """Verify that the correct path flag is rendered based on initialize_conda mode."""
    info = mock_info.copy()
    info["initialize_conda"] = initialize_conda
    payload = Payload(info)
    rendered_templates = payload.render_templates()

    run_installation = next(f for f in rendered_templates if f.name == "run_installation.bat")
    text = run_installation.read_text(encoding="utf-8")
    assert expected_flag in text
    assert "constructor windows path" in text


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
@pytest.mark.parametrize("no_rcs_arg", ["--no-rc", ""])
def test_render_templates_no_rcs_arg(no_rcs_arg):
    """Verify that no_rcs_arg is rendered into the template correctly."""
    info = mock_info.copy()
    info["_ignore_condarcs_arg"] = no_rcs_arg
    payload = Payload(info)
    rendered_templates = payload.render_templates()

    run_installation = next(f for f in rendered_templates if f.name == "run_installation.bat")
    text = run_installation.read_text(encoding="utf-8")
    if no_rcs_arg:
        assert no_rcs_arg in text


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_render_templates_registry_uses_base_path():
    """Test that Python registry entries use BASE_PATH (INSTDIR\\base) and not
    INSTDIR directly, since in the MSI layout is different from EXE."""
    info = mock_info.copy()
    info["_dists"] = ["python-3.11.5-0.tar.bz2"]
    payload = Payload(info)
    rendered_templates = payload.render_templates()

    run_installation = next(f for f in rendered_templates if f.name == "run_installation.bat")
    text = run_installation.read_text(encoding="utf-8")

    assert "%BASE_PATH%\\python.exe" in text
    assert "%BASE_PATH%\\Lib;%BASE_PATH%\\DLLs" in text
    assert "%BASE_PATH%\\Doc\\" in text

    assert "%INSTDIR%\\python.exe" not in text
    assert "%INSTDIR%\\Lib;%INSTDIR%\\DLLs" not in text
    assert "%INSTDIR%\\Doc\\" not in text


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_render_templates_nonadmin_created_for_user_install():
    """Verify that run_installation.bat creates a .nonadmin marker file
    when ALLUSERS is 0. This file is used by pre_uninstall.bat to determine
    the install mode via REG_HIVE."""
    info = mock_info.copy()
    payload = Payload(info)
    rendered_templates = payload.render_templates()

    run_installation = next(f for f in rendered_templates if f.name == "run_installation.bat")
    text = run_installation.read_text(encoding="utf-8")

    assert ".nonadmin" in text
    assert 'ALLUSERS%"=="0"' in text


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_render_templates_option_variable_names():
    """Verify that the option variable names in the rendered template match
    exactly what run_post_installation.bat sets via positional arguments."""
    info = mock_info.copy()
    info["_dists"] = ["python-3.11.5-0.tar.bz2"]
    payload = Payload(info)
    rendered_templates = payload.render_templates()

    run_installation = next(f for f in rendered_templates if f.name == "run_installation.bat")
    text = run_installation.read_text(encoding="utf-8")

    assert "OPTION_REGISTER_PYTHON" in text
    assert "OPTION_INITIALIZE_CONDA" in text
    assert "OPTION_CLEAR_PACKAGE_CACHE" in text
    assert "OPTION_ENABLE_SHORTCUTS" in text

    assert "OPTION_REGISTER_SYSTEM_PYTHON" not in text
    assert "OPTION_ADD_TO_PATH" not in text
    assert "OPTION_CLEAR_PKG_CACHE" not in text
    assert "OPTION_CREATE_SHORTCUTS" not in text


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_render_templates_uninstall_option_variable_names():
    """Verify that the uninstall option variable names in the rendered template match
    exactly what run_pre_uninstall.bat sets via positional arguments."""
    info = mock_info.copy()
    payload = Payload(info)
    rendered_templates = payload.render_templates()

    pre_uninstall = next(f for f in rendered_templates if f.name == "pre_uninstall.bat")
    text = pre_uninstall.read_text(encoding="utf-8")

    assert "OPTION_REMOVE_USER_DATA" in text
    assert "OPTION_REMOVE_CACHES" in text
    assert "OPTION_REMOVE_CONFIG_FILES" in text


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_pre_uninstall_delayed_expansion():
    """Verify that pre_uninstall.bat enables delayed expansion explicitly.
    This is required because:
    1. setlocal in pre_uninstall.bat creates a new scope, so enabledelayedexpansion
       from run_pre_uninstall.bat is NOT inherited.
    2. !VAR! syntax is needed inside for /f loops and for building UNINST_ARGS
       dynamically.
    """
    info = mock_info.copy()
    payload = Payload(info)
    rendered_templates = payload.render_templates()

    pre_uninstall = next(f for f in rendered_templates if f.name == "pre_uninstall.bat")
    text = pre_uninstall.read_text(encoding="utf-8")

    assert "setlocal enabledelayedexpansion" in text.lower()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_render_templates_no_python_no_registry():
    """Verify that when no Python dist is present, no registry operations
    appear in pre_uninstall.bat."""
    info = mock_info.copy()
    info["_dists"] = []
    payload = Payload(info)
    rendered_templates = payload.render_templates()

    pre_uninstall = next(f for f in rendered_templates if f.name == "pre_uninstall.bat")
    text = pre_uninstall.read_text(encoding="utf-8")

    assert "PythonCore" not in text
    assert "reg delete" not in text
    assert "reg query" not in text


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
@pytest.mark.parametrize(
    "initialize_conda, expected_flag",
    [
        ("condabin", "--condabin"),
        ("classic", "--classic"),
    ],
)
def test_render_templates_path_removal_flags(initialize_conda, expected_flag):
    """Verify the correct path flag is rendered in pre_uninstall.bat
    based on initialize_conda mode."""
    info = mock_info.copy()
    info["initialize_conda"] = initialize_conda
    payload = Payload(info)
    rendered_templates = payload.render_templates()

    pre_uninstall = next(f for f in rendered_templates if f.name == "pre_uninstall.bat")
    text = pre_uninstall.read_text(encoding="utf-8")

    assert expected_flag in text
    assert "constructor windows path" in text
    assert "--remove=user" in text


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_render_templates_path_removal_gated_on_nonadmin():
    """Verify that PATH removal in pre_uninstall.bat is gated on
    the .nonadmin marker file check, mirroring the NSIS behaviour. PATH was
    only ever added for user-scoped installs so should only be removed for
    those."""
    info = mock_info.copy()
    payload = Payload(info)
    rendered_templates = payload.render_templates()

    pre_uninstall = next(f for f in rendered_templates if f.name == "pre_uninstall.bat")
    text = pre_uninstall.read_text(encoding="utf-8")

    path_removal_pos = text.find("--remove=user")
    assert path_removal_pos != -1, '"--remove=user" not found in pre_uninstall.bat'

    # Search backwards from --remove=user to find the nearest preceding .nonadmin
    # guard, confirming it is the direct condition for PATH removal and not some
    # other .nonadmin check elsewhere in the file.
    preceding_text = text[:path_removal_pos]
    nonadmin_check_pos = preceding_text.rfind('if exist "%BASE_PATH%\\.nonadmin"')
    assert nonadmin_check_pos != -1, (
        'No .nonadmin guard found immediately before "--remove=user" in pre_uninstall.bat'
    )


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_render_templates_registry_uses_reg64():
    """Verify that Python registry writes in run_installation.bat use /reg:64
    to force the 64-bit registry view, since the MSI engine runs as a 32-bit
    process and would otherwise redirect writes to WOW6432Node."""
    info = mock_info.copy()
    info["_dists"] = ["python-3.11.5-0.tar.bz2"]
    payload = Payload(info)
    rendered_templates = payload.render_templates()

    run_installation = next(f for f in rendered_templates if f.name == "run_installation.bat")
    text = run_installation.read_text(encoding="utf-8")

    # REG64 variable must be defined and used
    assert "REG64" in text
    assert "/reg:64" in text
    # Must not use the literal flag directly in reg add calls (should use variable)
    assert "reg add" in text


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_pre_uninstall_registry_uses_reg64():
    """Verify that Python registry queries and deletes in pre_uninstall.bat use
    /reg:64 to force the 64-bit registry view, since the MSI engine runs as a
    32-bit process and registry entries were written to the 64-bit view at
    install time."""
    info = mock_info.copy()
    info["_dists"] = ["python-3.11.5-0.tar.bz2"]
    payload = Payload(info)
    rendered_templates = payload.render_templates()

    pre_uninstall = next(f for f in rendered_templates if f.name == "pre_uninstall.bat")
    text = pre_uninstall.read_text(encoding="utf-8")

    # REG64 variable must be defined and used in the subroutine
    assert "REG64" in text
    assert "/reg:64" in text

    # reg query and reg delete must both appear after the subroutine label
    subroutine_pos = text.find(":remove_python_registry")
    reg_query_pos = text.find("reg query", subroutine_pos)
    reg_delete_pos = text.find("reg delete", subroutine_pos)
    assert subroutine_pos != -1
    assert reg_query_pos != -1
    assert reg_delete_pos != -1

    # /reg:64 must appear in both the reg query and reg delete lines
    reg_query_line = next(
        line for line in text.splitlines() if "reg query" in line and "PythonCore" in line
    )
    reg_delete_line = next(line for line in text.splitlines() if "reg delete" in line)
    assert "/reg:64" in reg_query_line or "%REG64%" in reg_query_line
    assert "/reg:64" in reg_delete_line or "%REG64%" in reg_delete_line


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_pre_uninstall_conda_root_prefix():
    """Verify that CONDA_ROOT_PREFIX is set in pre_uninstall.bat.
    This is required for the --rm-menus command to work correctly."""
    info = mock_info.copy()
    payload = Payload(info)
    rendered_templates = payload.render_templates()

    pre_uninstall = next(f for f in rendered_templates if f.name == "pre_uninstall.bat")
    text = pre_uninstall.read_text(encoding="utf-8")

    assert "CONDA_ROOT_PREFIX=%BASE_PATH%" in text


def test_create_uninstall_options_list():
    """Test that create_uninstall_options_list returns all expected options."""
    options = create_uninstall_options_list({})

    option_names = [opt["name"] for opt in options]
    assert "remove_user_data" in option_names
    assert "remove_caches" in option_names
    assert "remove_config_files" in option_names


def test_render_templates_with_virtual_specs():
    """Test that virtual_specs check block is rendered when specs are provided."""
    info = mock_info.copy()
    info["virtual_specs"] = ["__win>=10", "__cuda>=11"]
    payload = Payload(info)
    rendered_templates = payload.render_templates()

    run_installation = next(f for f in rendered_templates if f.name == "run_installation.bat")
    text = run_installation.read_text(encoding="utf-8")

    assert "Checking virtual specs compatibility" in text
    assert '"__win>=10" "__cuda>=11"' in text
    assert "CONDA_SOLVER=classic" in text
    assert "--dry-run" in text
    assert "_virtual_specs_checks" in text


def test_render_templates_without_virtual_specs():
    """Test that virtual_specs check block is not rendered when specs are empty."""
    info = mock_info.copy()
    info["virtual_specs"] = []
    payload = Payload(info)
    rendered_templates = payload.render_templates()

    run_installation = next(f for f in rendered_templates if f.name == "run_installation.bat")
    text = run_installation.read_text(encoding="utf-8")

    assert "Checking virtual specs compatibility" not in text
    assert "_virtual_specs_checks" not in text


@pytest.mark.parametrize(
    "info",
    [
        {},
        {"script_env_variables": {}},
    ],
)
def test_get_script_env_variables_empty(info):
    """Test that empty dict is returned when no script_env_variables are provided."""
    assert _get_script_env_variables(info) == {}


@pytest.mark.parametrize(
    "script_env_variables, expected",
    [
        # Basic variables pass through
        ({"FOO": "bar"}, {"FOO": "bar"}),
        ({"FOO": "bar", "BAZ": "qux"}, {"FOO": "bar", "BAZ": "qux"}),
        # Single quotes are allowed
        ({"MSG": "foo 'bar'"}, {"MSG": "foo 'bar'"}),
        # Special batch characters are escaped
        ({"PERCENT": "50%"}, {"PERCENT": "50%%"}),
        ({"AMP": "a & b"}, {"AMP": "a ^& b"}),
        ({"PIPE": "a | b"}, {"PIPE": "a ^| b"}),
        ({"REDIR": "a < b > c"}, {"REDIR": "a ^< b ^> c"}),
        ({"CARET": "a^b"}, {"CARET": "a^^b"}),
        ({"BANG": "foo!"}, {"BANG": "foo^!"}),
    ],
)
def test_get_script_env_variables(script_env_variables, expected):
    """Test script_env_variables validation and escaping."""
    info = {"script_env_variables": script_env_variables}
    assert _get_script_env_variables(info) == expected


@pytest.mark.parametrize(
    "script_env_variables",
    [
        {"BAD": 'foo "bar"'},  # double quotes in value
        {'BAD"KEY': "value"},  # double quotes in key
    ],
)
def test_get_script_env_variables_double_quotes_rejected(script_env_variables):
    """Test that double quotes raise ValueError."""
    info = {"script_env_variables": script_env_variables}
    with pytest.raises(ValueError, match="double quotes"):
        _get_script_env_variables(info)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
@pytest.mark.parametrize("template_name", ["run_installation.bat", "pre_uninstall.bat"])
def test_render_templates_with_script_env_variables(template_name):
    """Test that script_env_variables are rendered in both install and uninstall templates."""
    info = mock_info.copy()
    info["script_env_variables"] = {"MY_VAR": "my_value", "OTHER": "50%"}
    payload = Payload(info)
    rendered_templates = payload.render_templates()

    template = next(f for f in rendered_templates if f.name == template_name)
    text = template.read_text(encoding="utf-8")

    assert 'set "MY_VAR=my_value"' in text
    assert 'set "OTHER=50%%"' in text


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
@pytest.mark.parametrize("template_name", ["run_installation.bat", "pre_uninstall.bat"])
def test_render_templates_without_script_env_variables(template_name):
    """Test that no script_env_variables block is rendered when not provided."""
    info = mock_info.copy()
    payload = Payload(info)
    rendered_templates = payload.render_templates()

    template = next(f for f in rendered_templates if f.name == template_name)
    text = template.read_text(encoding="utf-8")

    assert "User-defined environment variables" not in text


def test_setup_envs_commands_base_only():
    """Test _setup_envs_commands returns only base env when no extra_envs."""
    info = {
        "channels": ["conda-forge", "defaults"],
        "_extra_envs_info": {},
    }
    envs = _setup_envs_commands(info)

    assert len(envs) == 1
    assert envs[0]["name"] == "base"
    assert envs[0]["prefix"] == "%BASE_PATH%"
    assert envs[0]["lockfile"] == r"%BASE_PATH%\conda-meta\initial-state.explicit.txt"
    assert "conda-forge" in envs[0]["channels"]


def test_setup_envs_commands_with_extra_envs():
    """Test _setup_envs_commands includes extra_envs."""
    info = {
        "channels": ["defaults"],
        "_extra_envs_info": {
            "py311": {"_dists": []},
            "tools": {"_dists": []},
        },
        "extra_envs": {
            "py311": {
                "channels": ["conda-forge"],
            },
            "tools": {
                # No channels specified, should inherit from base
            },
        },
    }
    envs = _setup_envs_commands(info)

    assert len(envs) == 3

    # Base env
    assert envs[0]["name"] == "base"
    assert envs[0]["prefix"] == "%BASE_PATH%"

    # Extra envs
    env_names = [e["name"] for e in envs]
    assert "py311" in env_names
    assert "tools" in env_names

    py311_env = next(e for e in envs if e["name"] == "py311")
    assert py311_env["prefix"] == r"%BASE_PATH%\envs\py311"
    assert py311_env["lockfile"] == r"%BASE_PATH%\envs\py311\conda-meta\initial-state.explicit.txt"
    assert "conda-forge" in py311_env["channels"]

    tools_env = next(e for e in envs if e["name"] == "tools")
    assert tools_env["prefix"] == r"%BASE_PATH%\envs\tools"
    # tools inherits channels from base
    assert "defaults" in tools_env["channels"]


def test_setup_envs_commands_shortcuts():
    """Test _setup_envs_commands handles menu_packages/shortcuts correctly."""
    info = {
        "channels": ["defaults"],
        "menu_packages": ["console_shortcut"],
        "_extra_envs_info": {
            "myenv": {"_dists": []},
        },
        "extra_envs": {
            "myenv": {
                "menu_packages": ["other_shortcut"],
            },
        },
    }
    envs = _setup_envs_commands(info)

    assert len(envs) == 2

    base_env = envs[0]
    assert "console_shortcut" in base_env["shortcuts"]

    myenv = envs[1]
    assert "other_shortcut" in myenv["shortcuts"]


def test_setup_envs_commands_channels_remap():
    """Test _setup_envs_commands handles channels_remap correctly."""
    info = {
        "channels": ["https://foo.bar"],
        "channels_remap": [{"src": "https://foo.bar", "dest": "conda-forge"}],
        "_extra_envs_info": {
            "myenv": {"_dists": []},
        },
        "extra_envs": {
            "myenv": {
                "channels": ["https://foo.bar"],
                "channels_remap": [{"src": "https://foo.bar", "dest": "my-mirror"}],
            },
        },
    }
    envs = _setup_envs_commands(info)

    base_env = envs[0]
    assert "conda-forge" in base_env["channels"]

    myenv = envs[1]
    assert "my-mirror" in myenv["channels"]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
def test_render_templates_with_extra_envs():
    """Test that extra_envs are rendered in the install template."""
    info = mock_info.copy()
    info["channels"] = ["defaults"]
    info["_extra_envs_info"] = {
        "py311": {"_dists": []},
    }
    info["extra_envs"] = {
        "py311": {
            "channels": ["conda-forge"],
        },
    }
    payload = Payload(info)
    rendered_templates = payload.render_templates()

    run_installation = next(f for f in rendered_templates if f.name == "run_installation.bat")
    text = run_installation.read_text(encoding="utf-8")

    # Both base and py311 environments should be installed
    assert "Setting up base environment" in text
    assert "Setting up py311 environment" in text
    assert r"%BASE_PATH%\envs\py311" in text
