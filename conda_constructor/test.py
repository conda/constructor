from __future__ import print_function, division, absolute_import

import sys

import conda_constructor


def main():
    print('conda_constructor version:', conda_constructor.__version__)
    print('location:', conda_constructor.__file__)

    if sys.platform == 'win32':
        import conda_constructor.winexe as winexe

        winexe.read_nsi_tmpl()

    else:
        import conda_constructor.shar as shar

        shar.read_header_template()

    print("sys.prefix: %s" % sys.prefix)
    print("sys.version: %s" % sys.version)
    print("OK")


if __name__ == '__main__':
    main()
