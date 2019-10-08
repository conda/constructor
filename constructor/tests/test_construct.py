from ..construct import parse as construct_parse


def test_parse():
    p = construct_parse('constructor/tests/test_examples/construct.yaml', platform='osx-64')
    assert p['version'] == '2019.10'
    assert p['install_in_dependency_order']
    assert not p['keep_pkgs']
