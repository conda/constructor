import sys
from os.path import abspath, join

if 'develop' in sys.argv:
    import setuptools
from distutils.core import setup


setup(
    name = "constructor",
    version = "1.0.0",
    author = "Ilan Schnell",
    author_email = "ilan@continuum.io",
    license = "BSD",
    description = "create installer from conda packages",
    packages = ['constructor'],
    scripts = ['bin/conda-constructor'],
)


if 'install' in sys.argv:
    import shutil

    if sys.platform == 'win32':
        sp_dir = join(sys.prefix, 'Lib', 'site-packages')
        shutil.copytree(abspath('constructor/nsis'),
                        join(sp_dir, 'constructor', 'nsis'))

    else:
        sp_dir = join(sys.prefix, 'lib/python%d.%d/site-packages' %
                                               sys.version_info[:2])
        shutil.copy(abspath('constructor/header.sh'),
                    join(sp_dir, 'constructor'))
