import pytest
import re
from pathlib import Path
from constructor.briefcase import get_bundle_app_name, get_name_version, UninstallBat

THIS_DIR = Path(__file__).parent


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


def test_name_empty():
    with pytest.raises(ValueError, match="Name is empty"):
        get_name_version({"name": ""})


@pytest.mark.parametrize("version_in", ["", ".", "hello"])
def test_version_invalid(version_in):
    with pytest.raises(
        ValueError, match=f"Version {version_in!r} contains no valid version numbers"
    ):
        get_name_version(
            {"name": "Miniconda3", "version": version_in},
        )


@pytest.mark.parametrize(
    "rdi, name, bundle_expected, app_name_expected",
    [
        ("org.conda", "ignored", "org", "conda"),
        ("org.Conda", "ignored", "org", "Conda"),
        ("org.conda-miniconda", "ignored", "org", "conda-miniconda"),
        ("org.conda_miniconda", "ignored", "org", "conda_miniconda"),
        ("org-conda.miniconda", "ignored", "org-conda", "miniconda"),
        ("org.conda.miniconda", "ignored", "org.conda", "miniconda"),
        (None, "x", "io.continuum", "x"),
        (None, "X", "io.continuum", "x"),
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


@pytest.mark.parametrize("rdi", ["org.hello-", "org.-hello", "org.hello world", "org.hello!world"])
def test_rdi_invalid_package(rdi):
    with pytest.raises(
        ValueError,
        match=f"reverse_domain_identifier '{rdi}' doesn't end with a valid package name",
    ):
        get_bundle_app_name({"reverse_domain_identifier": rdi}, "ignored")


@pytest.mark.parametrize("name", ["", " ", "!", "-", "---"])
def test_name_no_alphanumeric(name):
    with pytest.raises(ValueError, match=f"Name '{name}' contains no alphanumeric characters"):
        get_bundle_app_name({}, name)

@pytest.mark.parametrize(
    "test_path",
    [
        Path("foo"),                         # relative path
        THIS_DIR,                            # absolute path of current test file
        THIS_DIR / "subdir",                 # absolute path to subdirectory
        Path.cwd() / "foo",                  # absolute path relative to working dir
    ],
)
def test_uninstall_bat_file_path(test_path):
    """Test that various directory inputs work as expected."""
    uninstall_bat = UninstallBat(test_path, user_script=None)
    assert uninstall_bat.file_path == test_path / 'pre_uninstall.bat'

@pytest.mark.parametrize("bat_file_name", ['foo.bat', 'bar.BAT'])
def test_bat_file_works(tmp_path, bat_file_name):
    """Test that both .bat and .BAT works and is considered a bat file."""
    uninstall_bat = UninstallBat(tmp_path, user_script=None)
    with open(uninstall_bat.file_path, 'w') as f:
        f.write("Hello")
    uninstall_bat.is_bat_file(uninstall_bat.file_path)

@pytest.mark.parametrize("bat_file_name", ['foo.bat', 'bar.BAT', 'foo.txt', 'bar'])
def test_invalid_user_script(tmp_path, bat_file_name):
    """Verify we get an exception if the user specifies an invalid type of pre_uninstall script."""
    expected = f"The entry '{bat_file_name}' configured via 'pre_uninstall' must be a path to an existing .bat file."
    with pytest.raises(ValueError, match=expected):
        UninstallBat(tmp_path, user_script = bat_file_name)

def test_sanitize_input_simple():
    """Test sanitize simple list."""
    items = ['foo', 'txt', 'exit']
    ubat = UninstallBat(Path('foo'), user_script=None)
    assert ubat.sanitize_input(items) == ['foo', 'txt', 'exit /b']

def test_sanitize_input_from_file(tmp_path):
    """Test sanitize input, also add a mix of newlines."""
    bat_file = tmp_path / 'test.bat'
    with open(bat_file, 'w') as f:
        f.writelines(['echo 1\n', 'exit\r\n', 'echo 2\n\n'])
    ubat = UninstallBat(tmp_path, user_script=bat_file)
    user_script = ubat.user_script_as_list()
    sanitized = ubat.sanitize_input(user_script)
    assert sanitized == ['echo 1', 'exit /b', '', 'echo 2', '']

def test_create_without_dir(tmp_path):
    """Verify we get an exception if the target directory does not exist"""
    dir_that_doesnt_exist = tmp_path / 'foo'
    ubat = UninstallBat(dir_that_doesnt_exist, user_script = None)
    expected = f"The directory {dir_that_doesnt_exist} must exist in order to create the file."
    with pytest.raises(FileNotFoundError, match=re.escape(expected)):
        ubat.create()

def test_create(tmp_path):
    """Verify the contents of the uninstall script looks as expected."""
    # TODO: Since we don't merge the user script right now, we need to account for this
    #       when it's been added.

    bat_file = tmp_path / 'test.bat'
    with open(bat_file, 'w') as f:
        f.writelines(['echo 1\n', 'exit\r\n', 'echo 2\n\n'])
    ubat = UninstallBat(tmp_path, user_script=bat_file)
    ubat.create()
    with open(ubat.file_path) as f:
        contents = f.readlines()
    expected = [
        '@echo off\n',
        'setlocal enableextensions enabledelayedexpansion\n',
        'set "_SELF=%~f0"\n',
        'set "_HERE=%~dp0"\n',
        '\n',
        'rem === Pre-uninstall script ===\n',
        '\n', 'rem User supplied with a script\n',
        '\n',
        'echo "hello from the script"\n',
        'pause\n'
    ]
    assert contents == expected
