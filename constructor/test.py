from __future__ import print_function, division, absolute_import

import sys

import constructor


def main():
    print('constructor version:', constructor.__version__)
    print('location:', constructor.__file__)

    if sys.platform == 'win32':
        import constructor.winexe as winexe

        winexe.read_nsi_tmpl()

    else:
        import constructor.shar as shar

        shar.read_header_template()

    print("sys.prefix: %s" % sys.prefix)
    print("sys.version: %s ..." % (sys.version[:40],))
    print("OK")


if __name__ == '__main__':
    main()
