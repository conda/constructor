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
import warnings

from .construct import ns_platform
from .imaging import write_images
from .install import name_dist
from .preconda import write_files as preconda_write_files
from .utils import filename_dist, fill_template, make_VIProductVersion, preprocess, add_condarc

THIS_DIR = dirname(__file__)
NSIS_DIR = join(THIS_DIR, 'nsis')
MAKENSIS_EXE = join(sys.prefix, 'NSIS', 'makensis.exe')


def str_esc(s):
    for a, b in [('$', '$$'), ('"', '$\\"'), ('\n', '$\\n'), ('\t', '$\\t')]:
        s = s.replace(a, b)
    return '"%s"' % s


def read_nsi_tmpl():
    path = join(NSIS_DIR, 'main.nsi.tmpl')
    print('Reading: %s' % path)
    with open(path) as fi:
        return fi.read()


def find_vs_runtimes(dists, py_version):
    valid_runtimes = (
        'vs2008_runtime',
        'vs2010_runtime',
        'vs2013_runtime',
        'vs2015_runtime',
        'msvc_runtime',
    )
    return [dist for dist in dists if name_dist(dist) in valid_runtimes]


def pkg_commands(download_dir, dists, py_version, keep_pkgs, attempt_hardlinks):
    vs_dists = find_vs_runtimes(dists, py_version)
    print("MSVC runtimes found: %s" % ([filename_dist(d) for d in vs_dists]))
    if len(vs_dists) != 1:
        warnings.warn("Number of MSVC runtimes found: %d" % len(vs_dists))

    # Extract MSVC runtimes and python to a temporary directory and delete it
    # later. This way we do not rely on PATH env var; and python, required for
    # invoking '.install.py', can pick up the required DLLs from it's vicinity.
    # NSIS doesn't provide direct functionality to create a temporary directory,
    # So we get the name of a temporary file, delete it and then create a
    # temporary directory by the same name.
    yield r'Var /Global ANACONDA_TMP_LOC'
    yield r"""System::Call 'Kernel32::GetTempFileName(t "$INSTDIR", t "t", i 0, t.r0) i.r1'"""
    yield r'StrCpy $ANACONDA_TMP_LOC $0'
    yield r'Delete $ANACONDA_TMP_LOC'
    yield r'CreateDirectory "$ANACONDA_TMP_LOC.dir"'

    assert filename_dist(dists[0]).startswith('python-')

    for n, dist in enumerate(vs_dists + dists[:1]):
        fn = filename_dist(dist)
        yield ''
        yield '# --> %s <--' % fn
        yield 'File %s' % str_esc(join(download_dir, fn))
        yield r'untgz::extract -d "$ANACONDA_TMP_LOC.dir" -zbz2 "$INSTDIR\pkgs\%s"' % fn

    for n, dist in enumerate(vs_dists + dists):
        fn = filename_dist(dist)
        yield ''
        yield '# --> %s <--' % fn
        if n > len(vs_dists):
            yield 'File %s' % str_esc(join(download_dir, fn))
        if attempt_hardlinks:
            yield r'untgz::extract -d "$INSTDIR\pkgs\%s" -zbz2 "$INSTDIR\pkgs\%s"' % (fn[:-8], fn)
        else:
            yield r'untgz::extract -d "$INSTDIR" -zbz2 "$INSTDIR\pkgs\%s"' % fn
            cmd = r'"$ANACONDA_TMP_LOC.dir\pythonw.exe" -E -s "$INSTDIR\pkgs\.install.py" --post root'
            yield "ExecWait '%s'" % cmd
        if keep_pkgs:
            continue
        yield r'Delete "$INSTDIR\pkgs\%s"' % fn

    if attempt_hardlinks:
        cmd = r'"$ANACONDA_TMP_LOC.dir\pythonw.exe" -E -s "$INSTDIR\pkgs\.install.py"'
        yield "ExecWait '%s'" % cmd

    if not keep_pkgs:
        yield ''
        yield r'RMDir "$INSTDIR\pkgs"'

    yield r'DetailPrint "Removing temporary files..."'
    # Turn off detail printing for the delete instruction
    yield r'SetDetailsPrint none'
    yield r'RMDir /r /REBOOTOK "$ANACONDA_TMP_LOC.dir"'
    yield r'SetDetailsPrint both'


def make_nsi(info, dir_path):
    "Creates the tmp/main.nsi from the template file"
    name = info['name']
    download_dir = info['_download_dir']
    dists = info['_dists']
    py_name, py_version, unused_build = filename_dist(dists[0]).rsplit('-', 2)
    assert py_name == 'python'
    arch = int(info['_platform'].split('-')[1])

    # these appear as __<key>__ in the template, and get escaped
    replace = {
        'NAME': name,
        'VERSION': info['version'],
        'VIPV': make_VIProductVersion(info['version']),
        'COMPANY': info.get('company', 'Unknown, Inc.'),
        'ARCH': '%d-bit' % arch,
        'PY_VER': py_version[:3],
        'PYVERSION': py_version,
        'PYVERSION_JUSTDIGITS': ''.join(py_version.split('.')),
        'OUTFILE': info['_outpath'],
        'LICENSEFILE': abspath(info.get('license_file',
                               join(NSIS_DIR, 'placeholder_license.txt'))),
        'DEFAULT_PREFIX': info.get(
            'default_prefix',
            join('%LOCALAPPDATA%', 'Continuum', name.lower())
        ),
    }
    for key, fn in [('HEADERIMAGE', 'header.bmp'),
                    ('WELCOMEIMAGE', 'welcome.bmp'),
                    ('ICONFILE', 'icon.ico'),
                    ('INSTALL_PY', '.install.py'),
                    ('URLS_FILE', 'urls'),
                    ('URLS_TXT_FILE', 'urls.txt'),
                    ('POST_INSTALL', 'post_install.bat'),
                    ('CONDA_HISTORY', join('conda-meta', 'history')),
                    ('REPODATA_RECORD', 'repodata_record.json'),
                    ('INDEX_CACHE', 'cache')]:
        replace[key] = join(dir_path, fn)
    for key in replace:
        replace[key] = str_esc(replace[key])

    data = read_nsi_tmpl()
    ppd = ns_platform(info['_platform'])
    ppd['initialize_by_default'] = info.get('initialize_by_default', None)
    ppd['register_python_default'] = info.get('register_python_default', None)
    data = preprocess(data, ppd)
    data = fill_template(data, replace)

    cmds = pkg_commands(download_dir, dists, py_version,
                        bool(info.get('keep_pkgs')),
                        bool(info.get('attempt_hardlinks')))

    # division by 10^3 instead of 2^10 is deliberate here. gives us more room
    approx_pkgs_size_kb = int(
        math.ceil(info.get('_approx_pkgs_size', 0) / 1000))

    # these are unescaped (and unquoted)
    for key, value in [
        ('@NAME@', name),
        ('@NSIS_DIR@', NSIS_DIR),
        ('@BITS@', str(arch)),
        ('@PKG_COMMANDS@', '\n    '.join(cmds)),
        ('@WRITE_CONDARC@', '\n    '.join(add_condarc(info))),
        ('@MENU_PKGS@', ' '.join(info.get('menu_packages', []))),
        ('@SIZE@', str(approx_pkgs_size_kb)),
        ('@UNINSTALL_NAME@', info.get('uninstall_name',
            '${NAME} ${VERSION} (Python ${PYVERSION} ${ARCH})'
        )),
        ]:
        data = data.replace(key, value)

    nsi_path = join(dir_path, 'main.nsi')
    with open(nsi_path, 'w') as fo:
        fo.write(data)
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
    out = check_output([MAKENSIS_EXE, '/VERSION'])
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
    if 'pre_install' in info:
        sys.exit("Error: Cannot run pre install on Windows, sorry.\n")

    post_dst = join(tmp_dir, 'post_install.bat')
    try:
        shutil.copy(info['post_install'], post_dst)
    except KeyError:
        with open(post_dst, 'w') as fo:
            fo.write(":: this is an empty post install .bat script\n")

    write_images(info, tmp_dir)
    nsi = make_nsi(info, tmp_dir)
    if verbose:
        verbosity = '/V4'
    else:
        verbosity = '/V2'
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
