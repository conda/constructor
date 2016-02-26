from constructor.fcp import parse_packages


PKGS_TXT = '''
# This is a test file
conda=3.17.0=py27_0
conda-build=1.17.0=py27_0
@EXPLICIT
#https://repo.continuum.io/pkgs/free/osx-64/openssl-1.0.1k-1.tar.bz2
https://repo.continuum.io/pkgs/free/osx-64/pip-7.1.2-py27_0.tar.bz2

pycosat-0.6.1-py27_0.tar.bz2
readline-6.2-2.tar.bz2#0801e644bd0c1cd7f0923b56c52eb7f7
https://repo.continuum.io/pkgs/free/osx-64/yaml-0.1.6-0.tar.bz2#7b1c018bf975c88fbe9df6292bf370b1
'''

RES = [
    (None, 'conda-3.17.0-py27_0.tar.bz2', None),
    (None, 'conda-build-1.17.0-py27_0.tar.bz2', None),
    ('https://repo.continuum.io/pkgs/free/osx-64/',
           'pip-7.1.2-py27_0.tar.bz2', None),
    (None, 'pycosat-0.6.1-py27_0.tar.bz2', None),
    (None, 'readline-6.2-2.tar.bz2', '0801e644bd0c1cd7f0923b56c52eb7f7'),
    ('https://repo.continuum.io/pkgs/free/osx-64/',
           'yaml-0.1.6-0.tar.bz2', '7b1c018bf975c88fbe9df6292bf370b1'),
]

def test_1():
    res = list(parse_packages(PKGS_TXT.splitlines()))
    assert res == RES

if __name__ == '__main__':
    test_1()
