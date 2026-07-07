from __future__ import annotations

from contextlib import nullcontext

import pytest

from constructor.fcp import check_duplicates, check_duplicates_files, exclude_packages


class GenericObject:
    """We use this for testing the check_duplicates function"""

    def __init__(self, name):
        self.name = name
        self.fn = "filename.txt"

    def __eq__(self, other):
        return self.name == other.name


@pytest.mark.parametrize(
    "values,expected_fails",
    (
        ((GenericObject("NameOne"), GenericObject("NameTwo"), GenericObject("NameTwo")), 1),
        ((GenericObject("NameOne"), GenericObject("NameTwo")), 0),
        ((GenericObject("NameOne"), GenericObject("NameTwo"), GenericObject("NameThree")), 0),
    ),
)
def test_check_duplicates(values: tuple[..., GenericObject], expected_fails: int):
    if expected_fails:
        context = pytest.raises(SystemExit)
    else:
        context = nullcontext()

    with context:
        check_duplicates(values)


@pytest.mark.parametrize(
    "values,expected_value",
    (
        (
            (
                (GenericObject("NameOne"), GenericObject("NameTwo"), GenericObject("NameThree")),
                ("NameThree",),
            ),
            [GenericObject("NameOne"), GenericObject("NameTwo")],
        ),
        (
            (
                (GenericObject("NameOne"), GenericObject("NameTwo"), GenericObject("NameThree")),
                ("Not in list",),
            ),
            False,
        ),
    ),
)
def test_exclude_packages(values: tuple[..., GenericObject], expected_value):
    if expected_value is False:
        context = pytest.raises(SystemExit)
    else:
        context = nullcontext()

    with context:
        packages = exclude_packages(*values)
        assert packages == expected_value


class MockPathData:
    """Represents a file path entry."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.size_in_bytes = 1  # must be non-zero to avoid filesystem access


class MockPathsJson:
    """Wraps a list of MockPathData entries."""

    def __init__(self, paths: list[str]) -> None:
        self.paths = [MockPathData(p) for p in paths]


class MockPackageCacheRecord:
    """Represents a package record."""

    def __init__(self, fn: str, extracted_package_dir: str, paths: list[str]) -> None:
        self.fn = fn
        self.extracted_package_dir = extracted_package_dir
        self._paths = paths

    def get(self, key: str, default: object = None) -> object:
        return default


def test_check_duplicates_files_returns_max_path_length(mocker):
    """Verify function returns max path length as third tuple element."""
    pc_rec1 = MockPackageCacheRecord(
        fn="pkg1-1.0.tar.bz2",
        extracted_package_dir="/cache/pkg1",  # basename "pkg1" (4)
        paths=["lib/short.py"],  # 12 chars
    )
    pc_rec2 = MockPackageCacheRecord(
        fn="pkg2-1.0.tar.bz2",
        extracted_package_dir="/cache/pkg2",  # basename "pkg2" (4)
        paths=["lib/python3.10/site-packages/longer.py"],  # 38 chars
    )

    def read_paths_side_effect(extracted_dir):
        if extracted_dir == "/cache/pkg1":
            return MockPathsJson(pc_rec1._paths)
        return MockPathsJson(pc_rec2._paths)

    mock_read_paths = mocker.patch("constructor.fcp.read_paths_json")
    mock_read_paths.side_effect = read_paths_side_effect

    result = check_duplicates_files([pc_rec1, pc_rec2], "win-64", duplicate_files="skip")

    assert len(result) == 3
    _, _, max_path_len = result
    # Longest is the pkgs-cache path for pkg2:
    # "pkgs/" (5) + "pkg2" (4) + "/" (1) + 38 = 48
    assert max_path_len == 48


def test_check_duplicates_files_accounts_for_pkgs_cache_path(mocker):
    """Max path length must account for the pkgs\\<pkgdir>\\ extraction prefix.

    Conda extracts each package into $INSTDIR\\pkgs\\<name-version-build>\\ before
    linking files to their final location. That intermediate path is longer than
    the final linked path and is what actually overflows MAX_PATH.
    """
    pc_rec = MockPackageCacheRecord(
        fn="madeuppkg-1.2.3.tar.bz2",
        # basename is the folder name used inside $INSTDIR\pkgs\
        extracted_package_dir="/cache/madeuppkg-1.2.3-h4567890_0",  # basename: 24 chars
        paths=["lib/x.py"],  # 8 chars, final linked path in base env
    )

    mock_read_paths = mocker.patch("constructor.fcp.read_paths_json")
    mock_read_paths.return_value = MockPathsJson(pc_rec._paths)

    result = check_duplicates_files([pc_rec], "win-64", duplicate_files="skip")

    # "pkgs/" (5) + "madeuppkg-1.2.3-h4567890_0" (26) + "/" (1) + "lib/x.py" (8) = 40
    assert result[2] == 40


def test_check_duplicates_files_long_env_name_beats_pkgs_path(mocker):
    """A long extra_envs name can make the linked path exceed the pkgs-cache path.

    The extraction path (pkgs/<pkgdir>/) and the final linked path
    (envs/<envname>/) are independent; whichever is longer for a given file must
    win. Here the env name is long enough that the linked path dominates.
    """
    pc_rec = MockPackageCacheRecord(
        fn="p-1.tar.bz2",
        extracted_package_dir="/cache/p-1-0",  # short basename "p-1-0" (5)
        paths=["lib/x.py"],  # 8 chars
    )

    mock_read_paths = mocker.patch("constructor.fcp.read_paths_json")
    mock_read_paths.return_value = MockPathsJson(pc_rec._paths)

    env_prefixes = {pc_rec: "envs/a-very-long-environment-name/"}  # 34 chars
    result = check_duplicates_files(
        [pc_rec], "win-64", duplicate_files="skip", env_prefixes=env_prefixes
    )

    # linked: "envs/a-very-long-environment-name/" (34) + "lib/x.py" (8) = 42
    # pkgs:   "pkgs/" (5) + "p-1-0" (5) + "/" (1) + "lib/x.py" (8) = 19
    # max is the linked path
    assert result[2] == 42


def test_check_duplicates_files_empty_packages(mocker):
    """Verify returns 0 when no packages provided."""
    mock_read_paths = mocker.patch("constructor.fcp.read_paths_json")

    result = check_duplicates_files([], "win-64", duplicate_files="skip")

    assert len(result) == 3
    assert result[2] == 0
    mock_read_paths.assert_not_called()


def test_check_duplicates_files_with_env_prefixes(mocker):
    """Verify env_prefixes adds prefix length to max path calculation."""
    pc_rec_base = MockPackageCacheRecord(
        fn="base-pkg-1.0.tar.bz2",
        extracted_package_dir="/cache/base-pkg",
        paths=["lib/short.py"],  # 12 chars, no prefix -> 12
    )
    pc_rec_env = MockPackageCacheRecord(
        fn="env-pkg-1.0.tar.bz2",
        extracted_package_dir="/cache/env-pkg",
        paths=["lib/short.py"],  # 12 chars, with "envs/myenv/" prefix (11) -> 23
    )

    def read_paths_side_effect(extracted_dir):
        if extracted_dir == "/cache/base-pkg":
            return MockPathsJson(pc_rec_base._paths)
        return MockPathsJson(pc_rec_env._paths)

    mock_read_paths = mocker.patch("constructor.fcp.read_paths_json")
    mock_read_paths.side_effect = read_paths_side_effect

    env_prefixes = {pc_rec_env: "envs/myenv/"}
    result = check_duplicates_files(
        [pc_rec_base, pc_rec_env], "win-64", duplicate_files="skip", env_prefixes=env_prefixes
    )

    assert len(result) == 3
    _, _, max_path_len = result
    # The pkgs-cache extraction path dominates the final linked path:
    # base-pkg: "pkgs/" (5) + "base-pkg" (8) + "/" (1) + "lib/short.py" (12) = 26
    # env-pkg:  "pkgs/" (5) + "env-pkg" (7) + "/" (1) + "lib/short.py" (12) = 25
    #           (final linked path "envs/myenv/" (11) + 12 = 23 is shorter)
    assert max_path_len == 26


def test_check_duplicates_files_env_prefix_normalizes_trailing_slash(mocker):
    """Verify env_prefixes without trailing slash are normalized."""
    pc_rec = MockPackageCacheRecord(
        fn="pkg-1.0.tar.bz2",
        extracted_package_dir="/cache/pkg",
        paths=["lib/file.py"],  # 11 chars
    )

    mock_read_paths = mocker.patch("constructor.fcp.read_paths_json")
    mock_read_paths.return_value = MockPathsJson(pc_rec._paths)

    # Missing trailing slash should be normalized (not raise error)
    env_prefixes = {pc_rec: "envs/myenv"}  # 10 chars, will become 11 with trailing /
    result = check_duplicates_files(
        [pc_rec], "win-64", duplicate_files="skip", env_prefixes=env_prefixes
    )

    # "envs/myenv/" (11) + "lib/file.py" (11) = 22
    assert result[2] == 22
