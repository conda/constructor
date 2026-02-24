import sys
import tarfile
from pathlib import Path

import pytest

from constructor.briefcase import Payload, get_bundle_app_name, get_name_version
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
    prepared_payload = payload.prepare()

    external_dir = prepared_payload.root / "external"
    assert external_dir.is_dir() and external_dir == prepared_payload.external

    base_dir = prepared_payload.root / "external" / "base"
    pkgs_dir = prepared_payload.root / "external" / "base" / "pkgs"
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
    prepared_payload = payload.prepare()

    assert prepared_payload.root.is_dir()
    payload.remove()
    assert not prepared_payload.root.is_dir()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_payload_pyproject_toml():
    """Test that the pyproject.toml file is created when the payload is prepared."""
    info = mock_info.copy()
    payload = Payload(info)
    prepared_payload = payload.prepare()
    pyproject_toml = prepared_payload.root / "pyproject.toml"
    assert pyproject_toml.is_file()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_payload_conda_exe():
    """Test that conda-standalone is prepared."""
    info = mock_info.copy()
    payload = Payload(info)
    prepared_payload = payload.prepare()
    conda_exe = prepared_payload.external / "_conda.exe"
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
    assert len(rendered_templates) == 2  # There should be at least two files

    for f in rendered_templates:
        assert f.is_file()

        with open(f) as open_file:
            lines = open_file.readlines()

        # Check the first line.
        expected = "@echo on\n" if debug_logging else "@echo off\n"
        assert lines[0] == expected
        # If debug_logging is True, we expect to find %LOG%, otherwise not.
        assert debug_logging == any("%LOG%" in line for line in lines)
