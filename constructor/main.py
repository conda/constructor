# (c) 2016 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from __future__ import print_function, division, absolute_import

import os
import sys
from os.path import abspath, dirname, isfile, join

from constructor.utils import read_ascii_only
import constructor.common as common


def read_dists(packages):
    res = []
    if isinstance(packages, list):
        res = packages
    else:
        for line in open(packages):
            line = line.strip()
            if line.startswith('#'):
                continue
            if '=' in line:
                res.append(line.replace('=', '-') + '.tar.bz2')
            else:
                res.append(line)
    return res


def get_output_filename(info):
    try:
        return info['installer_filename']
    except KeyError:
        pass

    osname, arch = info['platform'].split('-')
    os_map = {'linux': 'Linux', 'osx': 'MacOSX', 'win': 'Windows'}
    arch_name_map = {'64': 'x86_64', '32': 'x86'}
    ext = 'exe' if osname == 'win' else 'sh'
    return '%s-%s-%s.%s' % ('%(name)s-%(version)s' % info,
                            os_map.get(osname, osname),
                            arch_name_map.get(arch, arch),
                            ext)


def main_build(path, output_dir='.', verbose=True):
    info = common.parse_info(path)
    print('platform: %s' % info['platform'])

    for req in 'name', 'version', 'channels':
        if req not in info:
            sys.exit("Required key '%s' not found in %s" % (req, path))

    for key in 'license_file', 'welcome_image', 'header_image', 'icon_image':
        if key in info:
            info[key] = abspath(join(dirname(path), info[key]))

    if 'license_file' in info:
        info['_license_text'] = read_ascii_only(info['license_file'])

    common.set_index(info)
    if 'packages' in info:
        common.DISTS = read_dists(info['packages'])
    else:
        common.resolve(info)
        sys.stdout.write('\n')

    common.move_python_first()
    if verbose:
        common.show(info)
    common.check_dists()
    common.fetch(info)

    osname, unused_arch = info['platform'].split('-')
    if osname in ('linux', 'osx'):
        if sys.platform == 'win32':
            sys.exit("Error: Cannot create .sh installer on Windows platform.")
        from constructor.shar import create

    elif osname == 'win':
        if sys.platform != 'win32':
            sys.exit("Error: Cannot create Windows .exe installer on "
                     "non-Windows platform.")
        from winexe import create

    else:
        raise

    outpath = abspath(join(output_dir, get_output_filename(info)))
    info['_outpath'] = outpath
    create(info)
    print('Succussfully created %r.' % outpath)


def main():
    from optparse import OptionParser

    p = OptionParser(
        usage="usage: %prog [options] INSTALLER_SPEC_FILE",
        description="build an installer from an installer spec file")

    p.add_option('--debug',
                 action="store_true")

    p.add_option('--output-dir',
                 action="store",
                 default=os.getcwd(),
                 help='path to directory in which output installer is written '
                      'to, defaults to CWD (%default)',
                 metavar='PATH')

    p.add_option('--test',
                 help="perform some self tests and exit",
                 action="store_true")

    p.add_option('-v', '--verbose',
                 action="store_true")

    p.add_option('-V', '--version',
                 help="display the version being used and exit",
                 action="store_true")

    opts, args = p.parse_args()

    if opts.version:
        from constructor import __version__
        print('constructor version:', __version__)
        return

    if opts.test:
        import constructor.test
        constructor.test.main()
        return

    if opts.debug:
        import logging
        logging.basicConfig(level=logging.DEBUG)

    if len(args) != 1:
        p.error("exactly one argument expected")

    path = args[0]
    if not isfile(path):
        p.error("no such file: %s" % path)

    main_build(path, output_dir=opts.output_dir,
               verbose=opts.verbose)


if __name__ == '__main__':
    main()
