# (c) 2012-2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.
'''
We use the following conventions in this module:

    dist:        canonical package name, e.g. 'numpy-1.6.2-py26_0'

    ROOT_PREFIX: the prefix to the root environment, e.g. /opt/anaconda

    PKGS_DIR:    the "package cache directory", e.g. '/opt/anaconda/pkgs'
                 this is always equal to ROOT_PREFIX/pkgs

    prefix:      the prefix of a particular environment, which may also
                 be the root environment

Also, this module is directly invoked by the (self extracting) tarball
installer to create the initial environment, therefore it needs to be
standalone, i.e. not import any other parts of `conda` (only depend on
the standard library).
'''
from glob import glob
import os
import sys
import shutil
from os.path import islink
from argparse import ArgumentParser

from cpr import api as prefix_rename_api
from conda_package_handling import api as pkg_api


INSTALL_TMP_FOLDER = 'constructor_install'

on_win = bool(sys.platform == 'win32')
try:
    FORCE = bool(int(os.getenv('FORCE', 0)))
except ValueError:
    FORCE = False

LINK_HARD = 1
LINK_SOFT = 2  # never used during the install process
LINK_COPY = 3
link_name_map = {
    LINK_HARD: 'hard-link',
    LINK_SOFT: 'soft-link',
    LINK_COPY: 'copy',
}


def _link(src, dst, linktype=LINK_HARD):
    if linktype == LINK_HARD:
        if on_win:
            from ctypes import windll, wintypes
            CreateHardLink = windll.kernel32.CreateHardLinkW
            CreateHardLink.restype = wintypes.BOOL
            CreateHardLink.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR,
                                       wintypes.LPVOID]
            if not CreateHardLink(dst, src, None):
                raise OSError('win32 hard link failed')
        else:
            os.link(src, dst)
    elif linktype == LINK_COPY:
        # copy relative symlinks as symlinks
        if islink(src) and not os.readlink(src).startswith(os.path.sep):
            os.symlink(os.readlink(src), dst)
        else:
            shutil.copy2(src, dst)
    else:
        raise Exception("Did not expect linktype=%r" % linktype)


def _run_script(prefix, path):
    """
    call the post-link (or pre-unlink) script, and return True on success,
    False on failure
    """
    if on_win:
        try:
            args = [os.environ['COMSPEC'], '/c', path]
        except KeyError:
            return False
    else:
        shell_path = '/bin/sh' if 'bsd' in sys.platform else '/bin/bash'
        args = [shell_path, path]

    env = os.environ
    env['PREFIX'] = prefix

    import subprocess
    try:
        subprocess.check_call(args, env=env)
    except subprocess.CalledProcessError:
        return False
    return True


def unpack_archive(prefix):
    archive_file = os.path.join(prefix, "installer.conda")
    pkg_api.extract(archive_file, dest_dir=prefix)


def _run_install_scripts(prefix, script_ext, script_folder):
    # any user-defined pre-install scripts from the constructor config
    scripts = sorted(glob(os.path.join(prefix, INSTALL_TMP_FOLDER, script_folder, '*' + script_ext)))
    for script in scripts:
        _run_script(prefix, script)


def replace_hardcoded_prefixes(prefix):
    paths_file = os.path.join(prefix, INSTALL_TMP_FOLDER, 'has_prefix')
    prefix_rename_api.replace_paths(prefix, paths_file)


def relink_package_cache():
    """Installers are created from installed envs - without the packages, and with no cache at all.
    We need to recreate the package cache based on file metadata, so that subsequent envs can use our stuff."""
    pass


def run_pre_install_scripts(prefix, script_ext):
    return _run_install_scripts(prefix, script_ext, 'pre-install')


def run_post_link_scripts(prefix, script_ext):
    return _run_install_scripts(prefix, script_ext, 'post-link')


def run_post_install_scripts(prefix, script_ext):
    return _run_install_scripts(prefix, script_ext, 'post-install')


def error_on_special_chrs(prefix):
    if on_win:
        return
    SPECIAL_ASCII = '$!&\%^|{}[]<>~`"\':;?@*#'
    for c in SPECIAL_ASCII:
        if c in prefix:
            print("ERROR: found '%s' in install prefix.  Exiting - this would cause too many problems." % c)
            sys.exit(1)


def clean_up(prefix):
    # remove archive
    # remove INSTALL_TMP_FOLDER
    pass


def main():
    p = ArgumentParser(description="conda extract and script-running tool used by installers")
    p.add_argument('prefix', help='Path to folder containing archive; this is similar to the install destination.')
    p.add_argument('--skip-scripts', action="store_true", help="skip running post-link scripts")

    args = p.parse_args()
    error_on_special_chrs(args.prefix)

    unpack_archive(args.prefix)

    if not args.skip_scripts:
        run_pre_install_scripts(args.prefix)

    replace_hardcoded_prefixes(args.prefix)
    relink_package_cache(args.prefix)

    if not args.skip_scripts:
        run_post_link_scripts(args.prefix)
        run_post_install_scripts(args.prefix)
    clean_up(args.prefix)


if __name__ == '__main__':
    main()
