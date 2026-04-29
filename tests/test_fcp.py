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

    def __init__(self, path):
        self.path = path
        self.size_in_bytes = 1  # must be non-zero to avoid filesystem access


class MockPathsJson:
    """Wraps a list of MockPathData entries."""

    def __init__(self, paths):
        self.paths = [MockPathData(p) for p in paths]


class MockPackageCacheRecord:
    """Represents a package record."""

    def __init__(self, fn, extracted_package_dir, paths):
        self.fn = fn
        self.extracted_package_dir = extracted_package_dir
        self._paths = paths

    def get(self, key, default=None):
        return default


def test_check_duplicates_files_returns_max_path_length(mocker):
    """Verify function returns max path length as third tuple element."""
    pc_rec1 = MockPackageCacheRecord(
        fn="pkg1-1.0.tar.bz2",
        extracted_package_dir="/cache/pkg1",
        paths=["lib/short.py"],  # 12 chars
    )
    pc_rec2 = MockPackageCacheRecord(
        fn="pkg2-1.0.tar.bz2",
        extracted_package_dir="/cache/pkg2",
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
    assert max_path_len == 38


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
    # "envs/myenv/" (11) + "lib/short.py" (12) = 23
    assert max_path_len == 23
