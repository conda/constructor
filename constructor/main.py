# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from __future__ import absolute_import, division, print_function

import os
from os.path import abspath, basename, expanduser, isdir, join
import sys

from .conda_interface import cc_platform
from .construct import parse as construct_parse, verify as construct_verify
from .fcp import main as fcp_main
from .install import yield_lines

DEFAULT_CACHE_DIR = os.getenv('CONSTRUCTOR_CACHE', '~/.conda/constructor')


def set_installer_type(info):
    osname, unused_arch = info['_platform'].split('-')

    if not info.get('installer_type'):
        os_map = {'linux': 'sh', 'osx': 'sh', 'win': 'exe'}
        info['installer_type'] = os_map[osname]

    allowed_types = 'sh', 'pkg', 'exe'
    itype = info['installer_type']
    if itype not in allowed_types:
        sys.exit("Error: invalid installer type '%s',\n"
                 "allowed types are: %s" % (itype, allowed_types))

    if ((osname == 'linux' and itype != 'sh') or
        (osname == 'osx' and itype not in ('sh', 'pkg')) or
        (osname == 'win' and itype != 'exe')):
        sys.exit("Error: cannot create '.%s' installer for %s" % (itype,
                                                                  osname))


def get_output_filename(info):
    try:
        return info['installer_filename']
    except KeyError:
        pass

    osname, arch = info['_platform'].split('-')
    os_map = {'linux': 'Linux', 'osx': 'MacOSX', 'win': 'Windows'}
    arch_name_map = {'64': 'x86_64', '32': 'x86'}
    ext = info['installer_type']
    return '%s-%s-%s.%s' % ('%(name)s-%(version)s' % info,
                            os_map.get(osname, osname),
                            arch_name_map.get(arch, arch),
                            ext)


def main_build(dir_path, output_dir='.', platform=cc_platform,
               verbose=True, cache_dir=DEFAULT_CACHE_DIR,
               dry_run=False):
    print('platform: %s' % platform)
    cache_dir = abspath(expanduser(cache_dir))
    try:
        osname, unused_arch = platform.split('-')
    except ValueError:
        sys.exit("Error: invalid platform string '%s'" % platform)

    construct_path = join(dir_path, 'construct.yaml')
    info = construct_parse(construct_path, platform)
    construct_verify(info)
    info['_platform'] = platform
    info['_download_dir'] = join(cache_dir, platform)
    set_installer_type(info)

    if info['installer_type'] == 'sh':
        if sys.platform == 'win32':
            sys.exit("Error: Cannot create .sh installer on Windows.")
        from .shar import create
    elif info['installer_type'] == 'pkg':
        if sys.platform != 'darwin':
            sys.exit("Error: Can only create .pkg installer on OSX.")
        from .osxpkg import create
    elif info['installer_type'] == 'exe':
        if sys.platform != 'win32':
            sys.exit("Error: Can only create .pkg installer on Windows.")
        from .winexe import create

    if verbose:
        print('conda packages download: %s' % info['_download_dir'])

    for key in ('welcome_image_text', 'header_image_text'):
        if key not in info:
            info[key] = info['name']

    for key in ('license_file', 'welcome_image', 'header_image', 'icon_image',
                'pre_install', 'post_install'):
        if key in info:
            info[key] = abspath(join(dir_path, info[key]))

    for key in 'specs', 'packages':
        if key not in info:
            continue
        if isinstance(info[key], str):
            info[key] = list(yield_lines(join(dir_path, info[key])))

    for key in 'channels', 'specs', 'exclude', 'packages', 'menu_packages':
        if key in info:
            # ensure strings in those lists are stripped
            info[key] = [line.strip() for line in info[key]]
            # ensure there are no empty strings
            if any((not s) for s in info[key]):
                sys.exit("Error: found empty element in '%s:'" % key)

    fcp_main(info, verbose=verbose, dry_run=dry_run)
    if dry_run:
        print("Dry run, no installer created.")
        return

    info['_outpath'] = abspath(join(output_dir, get_output_filename(info)))

    # info has keys
    # 'name', 'version', 'channels', 'exclude',
    # '_platform', '_download_dir', '_outpath'
    # 'specs': ['python 3.5*', 'conda', 'nomkl', 'numpy', 'scipy', 'pandas', 'notebook', 'matplotlib', 'lighttpd']
    # 'license_file': '/Users/kfranz/continuum/constructor/examples/maxiconda/EULA.txt'
    # '_dists': List[Dist]
    # '_urls': List[Tuple[url, md5]]

    create(info, verbose=verbose)
    if 0:
        with open(join(output_dir, 'pkg-list.txt'), 'w') as fo:
            fo.write('# installer: %s\n' % basename(info['_outpath']))
            for dist in info['_dists']:
                fo.write('%s\n' % dist)
    print("Successfully created '%(_outpath)s'." % info)


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
                      "to, defaults to CWD ('%default')",
                 metavar='PATH')

    p.add_option('--cache-dir',
                 action="store",
                 default=DEFAULT_CACHE_DIR,
                 help='cache directory, used for downloading conda packages, '
                      'may be changed by CONSTRUCTOR_CACHE, '
                      "defaults to '%default'",
                 metavar='PATH')

    p.add_option('--clean',
                 action="store_true",
                 help='clean out the cache directory and exit')

    p.add_option('--platform',
                 action="store",
                 default=cc_platform,
                 help="the platform for which installer is for, "
                      "defaults to '%default'")

    p.add_option('--test',
                 help="perform some self tests and exit",
                 action="store_true")

    p.add_option('--dry-run',
                 help="solve package specs but do not create installer",
                 default=False,
                 action="store_true")

    p.add_option('-v', '--verbose',
                 action="store_true")

    p.add_option('-V', '--version',
                 help="display the version being used and exit",
                 action="store_true")

    opts, args = p.parse_args()

    if opts.version:
        from . import __version__
        print('constructor version:', __version__)
        return

    if opts.clean:
        import shutil
        cache_dir = abspath(expanduser(opts.cache_dir))
        print("cleaning cache: '%s'" % cache_dir)
        if isdir(cache_dir):
            shutil.rmtree(cache_dir)
        return

    if opts.test:
        from .tests import main as tests_main
        tests_main()
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
               verbose=opts.verbose, cache_dir=opts.cache_dir,
               dry_run=opts.dry_run)


if __name__ == '__main__':
    main()
