# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from __future__ import absolute_import, division, print_function

import os
from os.path import dirname
import sys

from . import test_install, test_utils
from .. import __file__ as CONSTRUCTOR_LOCATION, __version__ as CONSTRUCTOR_VERSION
from ..conda_interface import CONDA_INTERFACE_VERSION, conda_interface_type


def main():
    print("sys.prefix: %s" % sys.prefix)
    print("sys.version: %s ..." % (sys.version[:40],))
    print('constructor version:', CONSTRUCTOR_VERSION)
    print('conda interface type:', conda_interface_type)
    print('conda interface version:', CONDA_INTERFACE_VERSION)
    print('location:', dirname(CONSTRUCTOR_LOCATION))

    if sys.platform == 'win32':
        import PIL
        from .. import winexe
        from .test_imaging import test_write_images

        print('pillow version: %s' % PIL.PILLOW_VERSION)
        winexe.verify_nsis_install()
        winexe.read_nsi_tmpl()
        test_write_images()
    else: # Unix
        from .. import shar
        shar.read_header_template()

    if sys.platform == 'darwin':
        from ..osxpkg import OSX_DIR
        assert len(os.listdir(OSX_DIR)) == 6

    test_utils.main()
    assert test_install.run().wasSuccessful() == True


if __name__ == '__main__':
    main()
