# (c) 2016 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from __future__ import print_function, division, absolute_import

import os
import sys
from os.path import abspath, expanduser, isdir, join

from conda.config import subdir as cc_platform
from conda.install import yield_lines

import constructor.fcp as fcp
import constructor.construct as construct



def get_output_filename(info):
    try:
        return info['installer_filename']
    except KeyError:
        pass

    osname, arch = info['_platform'].split('-')
    os_map = {'linux': 'Linux', 'osx': 'MacOSX', 'win': 'Windows'}
    arch_name_map = {'64': 'x86_64', '32': 'x86'}
    ext = 'exe' if osname == 'win' else 'sh'
    return '%s-%s-%s.%s' % ('%(name)s-%(version)s' % info,
                            os_map.get(osname, osname),
                            arch_name_map.get(arch, arch),
                            ext)


def main_build(dir_path, output_dir='.', platform=cc_platform, verbose=True):
    print('platform: %s' % platform)
    try:
        osname, unused_arch = platform.split('-')
    except ValueError:
        sys.exit("Error: invalid platform string '%s'" % platform)

    if osname in ('linux', 'osx'):
        if sys.platform == 'win32':
            sys.exit("Error: Cannot create .sh installer on Windows platform.")
        from constructor.shar import create
    elif osname == 'win':
        if sys.platform != 'win32':
            sys.exit("Error: Cannot create Windows .exe installer on "
                     "non-Windows platform.")
        from constructor.winexe import create
    else:
        sys.exit("Error: invalid OS name '%s'" % osname)

    construct_path = join(dir_path, 'construct.yaml')
    info = construct.parse(construct_path, platform)
    construct.verify(info)
    info['_platform'] = platform
    info['_download_dir'] = join(expanduser('~'), '.conda', 'constructor',
                                 platform)
    if verbose:
        print('conda packages download: %s' % info['_download_dir'])

    for key in ('license_file', 'welcome_image', 'header_image', 'icon_image',
                'pre_install', 'post_install'):
        if key in info:
            info[key] = abspath(join(dir_path, info[key]))

    for key in 'specs', 'packages':
        if key not in info:
            continue
        if isinstance(info[key], str):
            info[key] = list(yield_lines(join(dir_path, info[key])))

    for key in 'channels', 'specs', 'exclude', 'packages':
        if key in info:
            # ensure strings in those lists are stripped
            info[key] = [line.strip() for line in info[key]]

    fcp.main(info, verbose=verbose)

    info['_outpath'] = join(output_dir, get_output_filename(info))
    create(info)
    print("Succussfully created '%(_outpath)s'." % info)


def main():
    from optparse import OptionParser

    p = OptionParser(
        usage="usage: %prog [options] DIRECTORY",
        description="build an installer from <DIRECTORY>/construct.yaml")

    p.add_option('--debug',
                 action="store_true")

    p.add_option('--output-dir',
                 action="store",
                 default=os.getcwd(),
                 help='path to directory in which output installer is written '
                      'to, defaults to CWD (%default)',
                 metavar='PATH')

    p.add_option('--platform',
                 action="store",
                 default=cc_platform,
                 help="the platform for which installer is for, "
                      "defaults to '%default'")

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
        import constructor.tests
        constructor.tests.main()
        return

    if opts.debug:
        import logging
        logging.basicConfig(level=logging.DEBUG)

    if len(args) != 1:
        p.error("exactly one argument expected")

    dir_path = args[0]
    if not isdir(dir_path):
        p.error("no such directory: %s" % dir_path)

    main_build(dir_path, output_dir=opts.output_dir, platform=opts.platform,
               verbose=opts.verbose)


if __name__ == '__main__':
    main()
