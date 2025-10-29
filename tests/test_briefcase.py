import pytest

from constructor.briefcase import get_bundle_app_name, get_name_version


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
