# (c) 2016 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from __future__ import print_function, division, absolute_import

import sys

import conda

import constructor
from constructor.tests import test_parser, test_utils


def main():
    print("sys.prefix: %s" % sys.prefix)
    print("sys.version: %s ..." % (sys.version[:40],))
    print('constructor version:', constructor.__version__)
    print('conda version:', conda.__version__)
    print('location:', constructor.__file__)

    if sys.platform == 'win32':
        import PIL
        import constructor.winexe as winexe
        from constructor.tests.test_imaging import test_write_images

        print('pillow version: %s' % PIL.PILLOW_VERSION)
        winexe.verify_nsis_install()
        winexe.read_nsi_tmpl()
        test_write_images()
    else:
        import constructor.shar as shar
        shar.read_header_template()

    test_parser.test_1()
    test_utils.main()
    print("OK")


if __name__ == '__main__':
    main()
