# (c) 2016 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from __future__ import print_function, division, absolute_import

import os
import sys
import shutil
import tempfile
from os.path import abspath, dirname, isfile, join
from subprocess import check_call

from constructor.construct import ns_platform
from constructor.utils import preprocess, name_dist
from constructor.imaging import write_images


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


def find_msvc_runtimes(dists, py_version):
    vs_map = {'2.7': 'vs2008_runtime',
              '3.4': 'vs2010_runtime',
              '3.5': 'vs2015_runtime'}
    vs_runtime = vs_map.get(py_version[:3])
    return [dist for dist in dists
            if name_dist(dist) in (vs_runtime, 'msvc_runtime')]


def make_nsi(info, dir_path):
    "Creates the tmp/main.nsi from the template file"
    data = read_nsi_tmpl()
    name = info['name']
    dists = info['_dists']
    py_name, py_version, unused_build = dists[0].rsplit('-', 2)
    assert py_name == 'python'

    arch = int(info['platform'].split('-')[1])
    license_path = abspath(info.get('license_file',
                                 join(NSIS_DIR, 'placeholder_license.txt')))

    data = preprocess(data, ns_platform(info['platform']))
    data = data.replace('__NAME__', str_esc(name))
    data = data.replace('__VERSION__', info['version'])
    data = data.replace('__COMPANY__', str_esc(info.get('company',
                                                        'Unknown, Inc.')))
    data = data.replace('__ARCH__', str_esc('%d-bit' % arch))
    data = data.replace('__PY_VER__', py_version[:3])
    data = data.replace('__PYVERSION__', str_esc(py_version))
    data = data.replace('__PYVERSION_JUSTDIGITS__',
                        str_esc(''.join(py_version.split('.'))))
    data = data.replace('__OUTFILE__', str_esc(info['_outpath']))
    data = data.replace('__LICENSEFILE__', str_esc(license_path))
    for placeholder, fn in [('__HEADERIMAGE__', 'header.bmp'),
                            ('__WELCOMEIMAGE__', 'welcome.bmp'),
                            ('__ICONFILE__', 'icon.ico')]:
        data = data.replace(placeholder, str_esc(join(dir_path, fn)))

    # these are unescaped (and unquoted)
    data = data.replace('@NAME@', name)
    data = data.replace('@NSIS_DIR@', NSIS_DIR)
    data = data.replace('@BITS@', str(arch))

    msvc_dists = find_msvc_runtimes(dists, py_version)
    if len(msvc_dists) != 1:
        sys.exit("Error: MSVC runtimes found: %s" % msvc_dists)

    pkg_commands = []
    for n, fn in enumerate(msvc_dists + dists):
        path = join(info['_download_dir'], fn)
        pkg_commands.append('# --> %s <--' % fn)
        pkg_commands.append('File %s' % str_esc(path))
        pkg_commands.append('untgz::extract "-d" "$INSTDIR" '
                            '"-zbz2" "$INSTDIR\pkgs\%s"' % fn)
        if n == 0:
            # only extract MSVC runtimes first, so that Python can be used
            # by _nsis postpkg
            assert 'runtime' in name_dist(fn)
            continue
        pkg_commands.append('ExecWait \'"$INSTDIR\pythonw.exe" '
                            '"$INSTDIR\Lib\_nsis.py" postpkg\'')
        pkg_commands.append('')

    data = data.replace('@PKG_COMMANDS@', '\n    '.join(pkg_commands))

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
    if not isfile(MAKENSIS_EXE):
        sys.exit("""
Error: no file %s
    please make sure nsis is installed:
    > conda install -n root nsis
""" % MAKENSIS_EXE)
    untgz_dll = join(sys.prefix, 'NSIS', 'Plugins', 'untgz.dll')
    if not isfile(untgz_dll):
         sys.exit("Error: no file %s")


def create(info):
    verify_nsis_install()
    tmp_dir = tempfile.mkdtemp()
    write_images(info, tmp_dir)
    nsi = make_nsi(info, tmp_dir)
    args = [MAKENSIS_EXE, '/V2', nsi]
    print('Calling: %s' % args)
    check_call(args)
    shutil.rmtree(tmp_dir)
