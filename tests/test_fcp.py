from __future__ import annotations

from unittest import mock

import pytest

from constructor.fcp import check_duplicates


class GenericObject:
    """We use this for testing the check_duplicates function"""
    def __init__(self, name):
        self.name = name
        self.fn = 'filename.txt'


@pytest.mark.parametrize('values,expected_fails', (
    (
        (GenericObject('NameOne'), GenericObject('NameTwo'), GenericObject('NameTwo')), 1
    ),
    (
        (GenericObject('NameOne'), GenericObject('NameTwo')), 0
    ),
    (
        (GenericObject('NameOne'), GenericObject('NameTwo'), GenericObject('NameThree')), 0
    ),
))
def test_check_duplicates(values: tuple[..., GenericObject], expected_fails: int):
    with mock.patch('constructor.fcp.sys.exit') as sys_exit:
        check_duplicates(values)
        assert len(sys_exit.mock_calls) == expected_fails
