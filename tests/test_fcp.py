from __future__ import annotations

from contextlib import nullcontext
from unittest.mock import patch

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


@patch("constructor.fcp.read_paths_json")
def test_check_duplicates_files_returns_max_path_length(mock_read_paths):
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

    mock_read_paths.side_effect = read_paths_side_effect

    result = check_duplicates_files([pc_rec1, pc_rec2], "win-64", duplicate_files="skip")

    assert len(result) == 3
    _, _, max_path_len = result
    assert max_path_len == 38


@patch("constructor.fcp.read_paths_json")
def test_check_duplicates_files_empty_packages(mock_read_paths):
    """Verify returns 0 when no packages provided."""
    result = check_duplicates_files([], "win-64", duplicate_files="skip")

    assert len(result) == 3
    assert result[2] == 0
    mock_read_paths.assert_not_called()
