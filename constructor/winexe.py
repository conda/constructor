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
from constructor.utils import preprocess, name_dist, fill_template
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


def find_vs_runtimes(dists, py_version):
    vs_map = {'2.7': 'vs2008_runtime',
              '3.4': 'vs2010_runtime',
              '3.5': 'vs2015_runtime'}
    vs_runtime = vs_map.get(py_version[:3])
    return [dist for dist in dists
            if name_dist(dist) in (vs_runtime, 'msvc_runtime')]


def pkg_commands(download_dir, dists, py_version):
    vs_dists = find_vs_runtimes(dists, py_version)
    print("MSVC runtimes found: %s" % vs_dists)
    if len(vs_dists) != 1:
        sys.exit("Error: number of MSVC runtimes found: %d" % len(vs_dists))

    for n, fn in enumerate(vs_dists + dists):
        yield ''
        yield '# --> %s <--' % fn
        yield 'File %s' % str_esc(join(download_dir, fn))
        yield ('untgz::extract "-d" "$INSTDIR" '
               '"-zbz2" "$INSTDIR\\pkgs\\%s"' % fn)
        if n == 0:
            # only extract MSVC runtimes first, so that Python can be used
            # by _nsis postpkg
            assert 'runtime' in name_dist(fn)
            continue
        if n == 1:
            assert name_dist(fn) == 'python'
        yield ('ExecWait \'"$INSTDIR\pythonw.exe" '
               '"$INSTDIR\\Lib\\_nsis.py" postpkg\'')


def make_nsi(info, dir_path):
    "Creates the tmp/main.nsi from the template file"
    name = info['name']
    download_dir = info['_download_dir']
    dists = info['_dists']
    py_name, py_version, unused_build = dists[0].rsplit('-', 2)
    assert py_name == 'python'
    arch = int(info['platform'].split('-')[1])

    # these appear as __<key>__ in the template, and get escaped
    replace = {
        'NAME': name,
        'VERSION': info['version'],
        'COMPANY': info.get('company', 'Unknown, Inc.'),
        'ARCH': '%d-bit' % arch,
        'PY_VER': py_version[:3],
        'PYVERSION': py_version,
        'PYVERSION_JUSTDIGITS': ''.join(py_version.split('.')),
        'OUTFILE': info['_outpath'],
        'LICENSEFILE': abspath(info.get('license_file',
                               join(NSIS_DIR, 'placeholder_license.txt'))),
    }
    for key, fn in [('HEADERIMAGE', 'header.bmp'),
                    ('WELCOMEIMAGE', 'welcome.bmp'),
                    ('ICONFILE', 'icon.ico')]:
        replace[key] = join(dir_path, fn)
    for key in replace:
        replace[key] = str_esc(replace[key])

    data = read_nsi_tmpl()
    data = preprocess(data, ns_platform(info['platform']))
    data = fill_template(data, replace)

    # these are unescaped (and unquoted)
    cmds = '\n    '.join(pkg_commands(download_dir, dists, py_version))
    for key, value in [('NAME', name),
                       ('NSIS_DIR', NSIS_DIR),
                       ('BITS', str(arch)),
                       ('PKG_COMMANDS', cmds)]:
        data = data.replace('@%s@' % key, value)

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


if __name__ == '__main__':
    make_nsi({'name': 'Maxi', 'version': '1.2',
              'platform': 'win-64',
              '_outpath': 'dummy.exe',
              '_download_dir': 'dummy',
              '_dists': ['python-2.7.9-0.tar.bz2',
                         'vs2008_runtime-1.0-1.tar.bz2']},
             '.')
