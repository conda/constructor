# (c) 2016 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import sys
from os.path import abspath, join

if 'develop' in sys.argv:
    import setuptools
from distutils.core import setup


setup(
    name = "constructor",
    version = "0.9.2",
    author = "Ilan Schnell",
    author_email = "ilan@continuum.io",
    license = "BSD",
    description = "create installer from conda packages",
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
