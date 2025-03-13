from __future__ import annotations

from contextlib import nullcontext

import pytest

from constructor.fcp import check_duplicates, exclude_packages


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
