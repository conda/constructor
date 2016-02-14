# (c) 2016 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from __future__ import print_function, division, absolute_import

import os
import sys
import shutil
import tarfile
import tempfile
from os.path import dirname, getsize, join

from conda.utils import md5_file
import conda.config
import conda.install

from constructor.utils import preprocess, read_ascii_only
import constructor.common as common


THIS_DIR = dirname(__file__)


def read_header_template():
    path = join(THIS_DIR, 'header.sh')
    print('Reading: %s' % path)
    with open(path) as fi:
        return fi.read()


def add_condarc(lines, info):
    lines.append('# ----- add condarc')
    lines.append('cat <<EOF >$PREFIX/.condarc')
    lines.append('default_channels:')
    for url in info['conda_default_channels']:
        lines.append('  - %s' % url)
    lines.append('EOF')


def get_header(tarball, info):
    data = read_header_template()

    name = info['name']
    dists0 = common.DISTS[0][:-8]
    py_name, py_version, unused_build = dists0.rsplit('-', 2)
    if py_name != 'python':
        sys.exit("Error: a Python package needs to be part of the "
                 "specifications")

    data = preprocess(data, common.ns_platform(info['platform']))

    # Needs to happen first -- can be templated
    data = data.replace('__NAME__', name)
    data = data.replace('__name__', name.lower())
    data = data.replace('__VERSION__', info['version'])
    data = data.replace('__DEFAULT_PREFIX__',
                        info.get('default_prefix', '$HOME/' + name.lower()))
    data = data.replace('__PLAT__', info['platform'])
    data = data.replace('__DIST0__', dists0)
    data = data.replace('__PY_VER__', py_version[:3])

    has_license = bool('license_file' in info)
    data = data.replace('__HAS_LICENSE__', str(int(has_license)))
    if has_license:
        data = data.replace('__LICENSE__',
                            read_ascii_only(info['license_file']))

    lines = ['install_dist %s' % (fn[:-8],) for fn in common.DISTS]
    if 'conda_default_channels' in info:
        add_condarc(lines, info)
    data = data.replace('__INSTALL_COMMANDS__', '\n'.join(lines))

    data = data.replace('__MD5__', md5_file(tarball))

    n = data.count('\n')
    data = data.replace('__LINES__', str(n + 1))

    # note that this replacement does not change the size of the header,
    # which would result into an inconsistency
    n = len(data) + getsize(tarball)
    data = data.replace('___BYTES___', '%11d' % n)

    return data


def create(info):
    tmp_dir = tempfile.mkdtemp()
    tarball = join(tmp_dir, 'tmp.tar')
    t = tarfile.open(tarball, 'w')
    if 'license_file' in info:
        t.add(info['license_file'], 'LICENSE.txt')
    for fn in common.DISTS:
        t.add(join(common.REPO_DIR, fn), 'tmp/' + fn)
    t.add(join(conda.install.__file__.rstrip('co')), 'tmp/install.py')
    t.add(join(THIS_DIR, 'post.py'), 'tmp/post.py')
    t.close()

    header = get_header(tarball, info)
    shar_path = info['_outpath']
    with open(shar_path, 'wb') as fo:
        fo.write(header.encode('utf-8'))
        with open(tarball, 'rb') as fi:
            while True:
                chunk = fi.read(262144)
                if not chunk:
                    break
                fo.write(chunk)

    os.unlink(tarball)
    os.chmod(shar_path, 0o755)
    shutil.rmtree(tmp_dir)
