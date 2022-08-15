# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from __future__ import absolute_import, division, print_function

import os
from os.path import abspath, dirname, isfile, join
import shutil
from subprocess import Popen, PIPE, check_call, check_output
import sys
import math
import tempfile
from pathlib import PureWindowsPath

from .construct import ns_platform
from .imaging import write_images
from .preconda import copy_extra_files, write_files as preconda_write_files
from .utils import (approx_size_kb, filename_dist, fill_template, make_VIProductVersion,
                    preprocess, add_condarc, get_final_channels)

THIS_DIR = abspath(dirname(__file__))
NSIS_DIR = join(THIS_DIR, 'nsis')
MAKENSIS_EXE = abspath(join(sys.prefix, 'NSIS', 'makensis.exe'))


def str_esc(s, newlines=True):
    maps = [('$', '$$'), ('"', '$\\"'), ('\t', '$\\t')]
    if newlines:
        maps.append(('\n', '$\\n'), ('\r', '$\\r'))
    for a, b in maps:
        s = s.replace(a, b)
    return '"%s"' % s


def read_nsi_tmpl(info):
    path = abspath(info.get('nsis_template', join(NSIS_DIR, 'main.nsi.tmpl')))
    print('Reading: %s' % path)
    with open(path) as fi:
        return fi.read()


def pkg_commands(download_dir, dists):
    for fn in dists:
        yield 'File %s' % str_esc(join(download_dir, fn))


def extra_files_commands(paths, common_parent):
    paths = sorted([PureWindowsPath(p) for p in paths])
    lines = []
    current_output_path = "$INSTDIR"
    for path in paths:
        relative_parent = path.relative_to(common_parent).parent
        output_path = f"$INSTDIR\\{relative_parent}"
        if output_path != current_output_path:
            lines.append(f"SetOutPath {output_path}")
            current_output_path = output_path
        lines.append(f"File {path}")
    return lines


def setup_envs_commands(info, dir_path):
    template = """
        # Set up {name} env
        SetDetailsPrint TextOnly
        DetailPrint "Setting up the {name} environment ..."
        SetDetailsPrint both
        # List of packages to install
        SetOutPath "{env_txt_dir}"
        File {env_txt_abspath}
        # A conda-meta\history file is required for a valid conda prefix
        SetOutPath "{conda_meta}"
        FileOpen $0 "history" w
        FileClose $0
        # Set channels
        System::Call 'kernel32::SetEnvironmentVariable(t,t)i("CONDA_CHANNELS", "{channels}").r0'
        # Run conda
        SetDetailsPrint TextOnly
        nsExec::ExecToLog '"$INSTDIR\_conda.exe" install --offline -yp "{prefix}" --file "{env_txt}" {shortcuts}'
        Pop $0
        SetDetailsPrint both
        # Cleanup {name} env.txt
        SetOutPath "$INSTDIR"
        Delete "{env_txt}"
        # Restore shipped conda-meta\history for remapped
        # channels and retain only the first transaction
        SetOutPath "{conda_meta}"
        File {history_abspath}
        """

    lines = template.format(  # this one block is for the base environment
        name="base",
        prefix=r"$INSTDIR",
        env_txt=r"$INSTDIR\pkgs\env.txt",  # env.txt as seen by the running installer
        env_txt_dir=r"$INSTDIR\pkgs",  # env.txt location in the installer filesystem
        env_txt_abspath=join(dir_path, "env.txt"), # env.txt location while building the installer
        conda_meta=r"$INSTDIR\conda-meta",
        history_abspath=join(dir_path, "conda-meta", "history"),
        channels=','.join(get_final_channels(info)),
        shortcuts="--no-shortcuts"
    ).splitlines()
    # now we generate one more block per extra env, if present
    for env_name in info.get("_extra_envs_info", {}):
        lines += ["", ""]
        env_info = info["extra_envs"][env_name]
        channel_info = {
            "channels": env_info.get("channels", info.get("channels", ())),
            "channels_remap": env_info.get("channels_remap", info.get("channels_remap", ()))
        }
        lines += template.format(
            name=env_name,
            prefix=join("$INSTDIR", "envs", env_name),
            env_txt=join("$INSTDIR", "pkgs", "envs", env_name, "env.txt"),
            env_txt_dir=join("$INSTDIR", "pkgs", "envs", env_name),
            env_txt_abspath=join(dir_path, "envs", env_name, "env.txt"),
            conda_meta=join("$INSTDIR", "envs", env_name, "conda-meta"),
            history_abspath=join(dir_path, "envs", env_name, "conda-meta", "history"),
            channels=",".join(get_final_channels(channel_info)),
            shortcuts="",
        ).splitlines()

    return [line.strip() for line in lines]


def make_nsi(info, dir_path, extra_files=()):
    "Creates the tmp/main.nsi from the template file"
    name = info['name']
    download_dir = info['_download_dir']

    dists = info['_dists'].copy()
    for env_info in info["_extra_envs_info"].values():
        dists += env_info["_dists"]
    dists = list({dist: None for dist in dists})  # de-duplicate

    py_name, py_version, unused_build = filename_dist(dists[0]).rsplit('-', 2)
    assert py_name == 'python'
    arch = int(info['_platform'].split('-')[1])
    info['post_install_desc'] = info.get('post_install_desc', "")
    conclusion_lines = info.get("conclusion_text", "").splitlines()

    # these appear as __<key>__ in the template, and get escaped
    replace = {
        'NAME': name,
        'VERSION': info['version'],
        'COMPANY': info.get('company', 'Unknown, Inc.'),
        'ARCH': '%d-bit' % arch,
        'PY_VER': ".".join(py_version.split(".")[:2]),
        'PYVERSION_JUSTDIGITS': ''.join(py_version.split('.')),
        'PYVERSION': py_version,
        'PYVERSION_MAJOR': py_version.split('.')[0],
        'DEFAULT_PREFIX': info.get('default_prefix', join('%USERPROFILE%', name.lower())),
        'DEFAULT_PREFIX_DOMAIN_USER': info.get('default_prefix_domain_user',
                                               join('%LOCALAPPDATA%', name.lower())),
        'DEFAULT_PREFIX_ALL_USERS': info.get('default_prefix_all_users',
                                             join('%ALLUSERSPROFILE%', name.lower())),

        'POST_INSTALL_DESC': info['post_install_desc'],
        'OUTFILE': info['_outpath'],
        'VIPV': make_VIProductVersion(info['version']),
        'ICONFILE': '@icon.ico',
        'HEADERIMAGE': '@header.bmp',
        'WELCOMEIMAGE': '@welcome.bmp',
        'LICENSEFILE': abspath(info.get('license_file', join(NSIS_DIR, 'placeholder_license.txt'))),
        'CONDA_HISTORY': '@' + join('conda-meta', 'history'),
        'CONDA_EXE': '@_conda.exe',
        'ENV_TXT': '@env.txt',
        'URLS_FILE': '@urls',
        'URLS_TXT_FILE': '@urls.txt',
        'POST_INSTALL': '@post_install.bat',
        'PRE_UNINSTALL': '@pre_uninstall.bat',
        'INDEX_CACHE': '@cache',
        'REPODATA_RECORD': '@repodata_record.json',
        'CONCLUSION_TITLE': str_esc(conclusion_lines[0].strip()),
        # See https://nsis.sourceforge.io/Docs/Modern%20UI/Readme.html#toggle_pgf
        # for the newlines business
        'CONCLUSION_TEXT': str_esc("\\r\\n".join(conclusion_lines[1:]), newlines=False),
    }
    for key, value in replace.items():
        if value.startswith('@'):
            value = join(dir_path, value[1:])
        replace[key] = str_esc(value)

    data = read_nsi_tmpl(info)
    ppd = ns_platform(info['_platform'])
    ppd['initialize_by_default'] = info.get('initialize_by_default', None)
    ppd['register_python_default'] = info.get('register_python_default', None)
    ppd['check_path_length'] = info.get('check_path_length', None)
    ppd['check_path_spaces'] = info.get('check_path_spaces', True)
    ppd['keep_pkgs'] = info.get('keep_pkgs') or False
    ppd['post_install_exists'] = bool(info.get('post_install'))
    ppd['with_conclusion_text'] = bool(info.get('conclusion_text')) or False
    data = preprocess(data, ppd)
    data = fill_template(data, replace)
    if info['_platform'].startswith("win") and sys.platform != 'win32':
        # Branding /TRIM commannd is unsupported on non win platform
        data_lines = data.split("\n")
        for i, line in enumerate(data_lines):
            if "/TRIM" in line:
                del data_lines[i]
                break
        data = "\n".join(data_lines)

    approx_pkgs_size_kb = approx_size_kb(info, "pkgs")

    # these are unescaped (and unquoted)
    for key, value in [
        ('@NAME@', name),
        ('@NSIS_DIR@', NSIS_DIR),
        ('@BITS@', str(arch)),
        ('@PKG_COMMANDS@', '\n    '.join(pkg_commands(download_dir, dists))),
        ('@SETUP_ENVS@', '\n    '.join(setup_envs_commands(info, dir_path))),
        ('@WRITE_CONDARC@', '\n    '.join(add_condarc(info))),
        ('@MENU_PKGS@', ' '.join(info.get('menu_packages', []))),
        ('@SIZE@', str(approx_pkgs_size_kb)),
        ('@UNINSTALL_NAME@', info.get('uninstall_name',
                                      '${NAME} ${VERSION} (Python ${PYVERSION} ${ARCH})'
                                      )),
        ('@EXTRA_FILES@', '\n    '.join(extra_files_commands(extra_files, dir_path))),
    ]:
        data = data.replace(key, value)

    nsi_path = join(dir_path, 'main.nsi')
    with open(nsi_path, 'w') as fo:
        fo.write(data)
    # Uncomment to see the file for debugging
    # with open('main.nsi', 'w') as fo:
    #     fo.write(data)
    # Copy all the NSIS header files (*.nsh)
    for fn in os.listdir(NSIS_DIR):
        if fn.endswith('.nsh'):
            shutil.copy(join(NSIS_DIR, fn),
                        join(dir_path, fn))

    print('Created %s file' % nsi_path)
    return nsi_path


def verify_nsis_install():
    print("Checking for '%s'" % MAKENSIS_EXE)
    if not isfile(MAKENSIS_EXE):
        sys.exit("""
Error: no file %s
    please make sure nsis is installed:
    > conda install nsis
""" % MAKENSIS_EXE)
    if sys.platform == "win32":
        out = check_output([MAKENSIS_EXE, '/VERSION'])
    else:
        out = check_output([MAKENSIS_EXE, '-VERSION'])
    out = out.decode('utf-8').strip()
    print("NSIS version: %s" % out)
    for dn in 'x86-unicode', 'x86-ansi', '.':
        untgz_dll = abspath(join(sys.prefix, 'NSIS',
                                 'Plugins', dn, 'untgz.dll'))
        if isfile(untgz_dll):
            break
    else:
        sys.exit("Error: no file untgz.dll")


def create(info, verbose=False):
    verify_nsis_install()
    tmp_dir = tempfile.mkdtemp()
    preconda_write_files(info, tmp_dir)
    copied_extra_files = copy_extra_files(info, tmp_dir)
    shutil.copyfile(info['_conda_exe'], join(tmp_dir, '_conda.exe'))

    if 'pre_install' in info:
        sys.exit("Error: Cannot run pre install on Windows, sorry.\n")

    post_dst = join(tmp_dir, 'post_install.bat')
    try:
        shutil.copy(info['post_install'], post_dst)
    except KeyError:
        with open(post_dst, 'w') as fo:
            fo.write(":: this is an empty post install .bat script\n")

    pre_dst = join(tmp_dir, 'pre_uninstall.bat')
    try:
        shutil.copy(info['pre_uninstall'], pre_dst)
    except KeyError:
        with open(pre_dst, 'w') as fo:
            fo.write(":: this is an empty pre uninstall .bat script\n")

    write_images(info, tmp_dir)
    nsi = make_nsi(info, tmp_dir, extra_files=copied_extra_files)
    if verbose:
        verbosity = 'V4'
    else:
        verbosity = 'V2'
    if sys.platform == "win32":
        verbosity = "/" + verbosity
    else:
        verbosity = "-" + verbosity
    args = [MAKENSIS_EXE, verbosity, nsi]
    print('Calling: %s' % args)
    if verbose:
        sub = Popen(args, stdout=PIPE, stderr=PIPE)
        stdout, stderr = sub.communicate()
        for msg, information in zip((stdout, stderr), ('stdout', 'stderr')):
            # on Python3 we're getting bytes
            if hasattr(msg, 'decode'):
                msg = msg.decode()
            print('makensis {}:'.format(information))
            print(msg)
    else:
        check_call(args)
    shutil.rmtree(tmp_dir)


if __name__ == '__main__':
    make_nsi({'name': 'Maxi', 'version': '1.2',
              '_platform': 'win-64',
              '_outpath': 'dummy.exe',
              '_download_dir': 'dummy',
              '_dists': ['python-2.7.9-0.tar.bz2',
                         'vs2008_runtime-1.0-1.tar.bz2']},
             '.')
