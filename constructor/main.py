# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.


import argparse
import logging
import os
import sys
from os.path import abspath, expanduser, isdir, join
from textwrap import dedent, indent

from . import __version__
from .build_outputs import process_build_outputs
from .conda_interface import SUPPORTED_PLATFORMS, cc_platform
from .construct import generate_key_info_list, ns_platform
from .construct import parse as construct_parse
from .construct import verify as construct_verify
from .fcp import main as fcp_main
from .utils import normalize_path, yield_lines

DEFAULT_CACHE_DIR = os.getenv('CONSTRUCTOR_CACHE', '~/.conda/constructor')

logger = logging.getLogger(__name__)


def get_installer_type(info):
    osname, unused_arch = info['_platform'].split('-')

    os_allowed = {'linux': ('sh',), 'osx': ('sh', 'pkg'), 'win': ('exe',)}
    all_allowed = set(sum(os_allowed.values(), ('all',)))

    itype = info.get('installer_type')
    if not itype:
        return os_allowed[osname][:1]
    elif itype == 'all':
        return os_allowed[osname]
    elif itype not in all_allowed:
        all_allowed = ', '.join(sorted(all_allowed))
        sys.exit("Error: invalid installer type '%s'; allowed: %s" % (itype, all_allowed))
    elif itype not in os_allowed[osname]:
        os_allowed = ', '.join(sorted(os_allowed[osname]))
        sys.exit("Error: invalid installer type '%s' for %s; allowed: %s" %
                 (itype, osname, os_allowed))
    else:
        return itype,


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
               dry_run=False, conda_exe="conda.exe"):
    logger.info('platform: %s', platform)
    if not os.path.isfile(conda_exe):
        sys.exit("Error: Conda executable '%s' does not exist!" % conda_exe)
    cache_dir = abspath(expanduser(cache_dir))
    try:
        osname, unused_arch = platform.split('-')
    except ValueError:
        sys.exit("Error: invalid platform string '%s'" % platform)

    construct_path = join(dir_path, 'construct.yaml')
    info = construct_parse(construct_path, platform)
    construct_verify(info)
    info['CONSTRUCTOR_VERSION'] = __version__
    info['_input_dir'] = dir_path
    info['_output_dir'] = output_dir
    info['_platform'] = platform
    info['_download_dir'] = join(cache_dir, platform)
    info['_conda_exe'] = abspath(conda_exe)
    itypes = get_installer_type(info)

    if platform != cc_platform and 'pkg' in itypes and not cc_platform.startswith('osx-'):
        sys.exit("Error: cannot construct a macOS 'pkg' installer on '%s'" % cc_platform)


    logger.debug('conda packages download: %s', info['_download_dir'])

    for key in ('welcome_image_text', 'header_image_text'):
        if key not in info:
            info[key] = info['name']

    for key in ('license_file', 'welcome_image', 'header_image', 'icon_image',
                'pre_install', 'post_install', 'pre_uninstall', 'environment_file',
                'nsis_template', 'welcome_file', 'readme_file', 'conclusion_file',
                'signing_certificate'):
        if info.get(key):  # only join if there's a truthy value set
            info[key] = abspath(join(dir_path, info[key]))

    for key in 'specs', 'packages':
        if key not in info:
            continue
        if isinstance(info[key], str):
            info[key] = list(yield_lines(join(dir_path, info[key])))

    # normalize paths to be copied; if they are relative, they must be to
    # construct.yaml's parent (dir_path)
    extras_types = ['extra_files', 'temp_extra_files']
    for extra_type in extras_types:
        extras = info.get(extra_type, ())
        new_extras = []
        for path in extras:
            if isinstance(path, str):
                new_extras.append(abspath(join(dir_path, path)))
            elif isinstance(path, dict):
                assert len(path) == 1
                orig, dest = next(iter(path.items()))
                orig = abspath(join(dir_path, orig))
                new_extras.append({orig: dest})
        info[extra_type] = new_extras

    for key in 'channels', 'specs', 'exclude', 'packages', 'menu_packages':
        if key in info:
            # ensure strings in those lists are stripped
            info[key] = [line.strip() for line in info[key]]
            # ensure there are no empty strings
            if any((not s) for s in info[key]):
                sys.exit("Error: found empty element in '%s:'" % key)

    for env_name, env_config in info.get("extra_envs", {}).items():
        if env_name in ("base", "root"):
            raise ValueError(f"Environment name '{env_name}' cannot be used")
        for config_key, value in env_config.copy().items():
            if isinstance(value, (list, tuple)):
                env_config[config_key] = [val.strip() for val in value]
            if config_key == "environment_file":
                env_config[config_key] = abspath(join(dir_path, value))

    info['installer_type'] = itypes[0]
    fcp_main(info, verbose=verbose, dry_run=dry_run, conda_exe=conda_exe)
    if dry_run:
        logger.info("Dry run, no installers or build outputs created.")
        return

    # info has keys
    # 'name', 'version', 'channels', 'exclude',
    # '_platform', '_download_dir', '_outpath'
    # 'specs': ['python 3.5*', 'conda', 'nomkl', 'numpy', 'scipy', 'pandas',
    #           'notebook', 'matplotlib', 'lighttpd']
    # 'license_file': '/Users/kfranz/continuum/constructor/examples/miniconda/EULA.txt'
    # '_dists': List[Dist]
    # '_urls': List[Tuple[url, md5]]

    for itype in itypes:
        if itype == 'sh':
            from .shar import create as shar_create
            create = shar_create
        elif itype == 'pkg':
            from .osxpkg import create as osxpkg_create
            create = osxpkg_create
        elif itype == 'exe':
            from .winexe import create as winexe_create
            create = winexe_create
        info['installer_type'] = itype
        info['_outpath'] = abspath(join(output_dir, get_output_filename(info)))
        create(info, verbose=verbose)
        logger.info("Successfully created '%(_outpath)s'.", info)

    process_build_outputs(info)


class _HelpConstructAction(argparse.Action):
    def __init__(
        self,
        option_strings,
        dest=argparse.SUPPRESS,
        default=argparse.SUPPRESS,
        help="describe available configuration options for construct.yaml files and exit",
    ):
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help,
        )

    def __call__(self, parser, namespace, values, option_string=None):

        parser._print_message(self._build_message(), sys.stdout)
        parser.exit()

    def _build_message(self):
        msg = dedent(
            """
            The 'construct.yaml' specification
            ==================================

            constructor version {version}

            The `construct.yaml` file is the primary mechanism for controlling
            the output of the Constructor package. The file contains a list of
            key/value pairs in the standard YAML format.

            Available keys
            --------------

            {available_keys}

            Available selectors
            -------------------

            Constructor can use the same Selector enhancement of the YAML format
            used in conda-build ('# [selector]'). Available keywords are:

            {available_selectors}
            """
        )
        available_keys_list = []
        for key, required, key_types, help_msg, plural in generate_key_info_list():
            available_keys_list.append(
                "\n".join(
                    [
                        key,
                        "·" * len(key),
                        indent(
                            f"Required: {required}, type{plural}: {key_types}", "    "
                        ),
                        indent(help_msg.strip(), "    "),
                        "",
                    ]
                )
            )
        available_selectors_list = [
            f"- {sel}" for sel in sorted(ns_platform(sys.platform).keys())
        ]
        return msg.format(
            version=__version__,
            available_keys="\n".join(available_keys_list),
            available_selectors="\n".join(available_selectors_list),
        )


def main():
    logging.basicConfig(level=logging.INFO)
    p = argparse.ArgumentParser(
        description="build an installer from <DIRECTORY>/construct.yaml")

    p.add_argument("--help-construct", action=_HelpConstructAction)

    p.add_argument('--debug',
                   action="store_true")

    p.add_argument('--output-dir',
                   action="store",
                   default=os.getcwd(),
                   help='path to directory in which output installer is written '
                   "to, defaults to CWD ('{}')".format(os.getcwd()),
                   metavar='PATH')

    p.add_argument('--cache-dir',
                   action="store",
                   default=DEFAULT_CACHE_DIR,
                   help='cache directory, used for downloading conda packages, '
                   'may be changed by CONSTRUCTOR_CACHE, '
                   "defaults to '{}'".format(DEFAULT_CACHE_DIR),
                   metavar='PATH')

    p.add_argument('--clean',
                   action="store_true",
                   help='clean out the cache directory and exit')

    p.add_argument('--platform',
                   action="store",
                   default=cc_platform,
                   help="the platform for which installer is for, "
                   f"defaults to '{cc_platform}'. Options, e.g.: {SUPPORTED_PLATFORMS}")

    p.add_argument('--dry-run',
                   help="solve package specs but do not create installer",
                   default=False,
                   action="store_true")

    p.add_argument('-v', '--verbose',
                   action="store_true")

    p.add_argument('-V', '--version',
                   help="display the version being used and exit",
                   action="version",
                   version=f'%(prog)s {__version__}')

    p.add_argument('--conda-exe',
                   help="path to conda executable (conda-standalone, micromamba)",
                   action="store",
                   metavar="CONDA_EXE")

    p.add_argument('dir_path',
                   help="directory containing construct.yaml",
                   action="store",
                   nargs="?",
                   default=os.getcwd(),
                   metavar='DIRECTORY')

    args = p.parse_args()
    logger.info("Got the following cli arguments: '%s'", args)

    if args.verbose or args.debug:
        logging.getLogger("constructor").setLevel(logging.DEBUG)

    if args.clean:
        import shutil
        cache_dir = abspath(expanduser(args.cache_dir))
        logger.info("cleaning cache: '%s'", cache_dir)
        if isdir(cache_dir):
            shutil.rmtree(cache_dir)
        return

    dir_path = args.dir_path
    if not isdir(dir_path):
        p.error("no such directory: %s" % dir_path)

    conda_exe = args.conda_exe
    conda_exe_default_path = os.path.join(sys.prefix, "standalone_conda", "conda.exe")
    conda_exe_default_path = normalize_path(conda_exe_default_path)
    if conda_exe:
        conda_exe = normalize_path(os.path.abspath(conda_exe))
    elif args.platform != cc_platform:
        p.error("setting --conda-exe is required for building a non-native installer")
    else:
        conda_exe = conda_exe_default_path
    if not os.path.isfile(conda_exe):
        if conda_exe != conda_exe_default_path:
            p.error("file not found: %s" % args.conda_exe)
        p.error("""
no standalone conda executable was found. The
easiest way to obtain one is to install the 'conda-standalone' package.
Alternatively, you can download an executable manually and supply its
path with the --conda-exe argument. Self-contained executables can be
downloaded from https://repo.anaconda.com/pkgs/misc/conda-execs/""".lstrip())

    out_dir = normalize_path(args.output_dir)
    main_build(dir_path, output_dir=out_dir, platform=args.platform,
               verbose=args.verbose, cache_dir=args.cache_dir,
               dry_run=args.dry_run, conda_exe=conda_exe)


if __name__ == '__main__':
    main()
