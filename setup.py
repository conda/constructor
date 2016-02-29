# (c) 2016 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import re
import sys
from os.path import abspath, join

if 'develop' in sys.argv:
    import setuptools
from distutils.core import setup


# read version from constructor/__init__.py
pat = re.compile(r'__version__\s*=\s*(\S+)', re.M)
data = open(join('constructor', '__init__.py')).read()
version = eval(pat.search(data).group(1))

setup(
    name = "constructor",
    version = version,
    author = "Ilan Schnell",
    author_email = "ilan@continuum.io",
    url = "https://github.com/conda/constructor",
    license = "BSD",
    description = "create installer from conda packages",
    long_description = open('README.md').read(),
    packages = ['constructor', 'constructor.tests'],
    scripts = ['bin/constructor'],
)


if 'install' in sys.argv:
    import shutil

    if sys.platform == 'win32':
        sp_dir = join(sys.prefix, 'Lib', 'site-packages')
        for dn in 'nsis', 'ttf':
            shutil.copytree(abspath(join('constructor', dn)),
                            join(sp_dir, 'constructor', dn))

    else:
        sp_dir = join(sys.prefix, 'lib/python%d.%d/site-packages' %
                                               sys.version_info[:2])
        shutil.copy(abspath('constructor/header.sh'),
                    join(sp_dir, 'constructor'))
