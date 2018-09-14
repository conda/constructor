# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from __future__ import absolute_import, division, print_function

import os
from os.path import basename, dirname, getsize, isdir, join
import json
import shutil
import tarfile
import tempfile

from .construct import ns_platform
from .install import name_dist
from .preconda import files as preconda_files, write_files as preconda_write_files
from .utils import add_condarc, filename_dist, fill_template, md5_file, preprocess, read_ascii_only

THIS_DIR = dirname(__file__)


def read_header_template():
    path = join(THIS_DIR, 'header.sh')
    print('Reading: %s' % path)
    with open(path) as fi:
        return fi.read()


def get_header(tarball, info):
    name = info['name']
    dists = [filename_dist(dist)[:-8] for dist in info['_dists']]
    dist0 = dists[0]
    assert name_dist(dist0) == 'python'

    has_license = bool('license_file' in info)
    ppd = ns_platform(info['_platform'])
    ppd['keep_pkgs'] = bool(info.get('keep_pkgs'))
    ppd['attempt_hardlinks'] = bool(info.get('attempt_hardlinks'))
    ppd['has_license'] = has_license
    for key in 'pre_install', 'post_install':
        ppd['has_%s' % key] = bool(key in info)
    ppd['initialize_by_default'] = info.get('initialize_by_default', None)

    install_lines = ['install_dist %s' % d for d in dists]
    install_lines.extend(add_condarc(info))
    # Needs to happen first -- can be templated
    replace = {
        'NAME': name,
        'name': name.lower(),
        'VERSION': info['version'],
        'PLAT': info['_platform'],
        'DIST0': dist0,
        'DEFAULT_PREFIX': info.get('default_prefix',
                                   '$HOME/%s' % name.lower()),
        'MD5': md5_file(tarball),
        'INSTALL_COMMANDS': '\n'.join(install_lines),
        'pycache': '__pycache__',
    }
    if has_license:
        replace['LICENSE'] = read_ascii_only(info['license_file'])

    data = read_header_template()
    data = preprocess(data, ppd)
    data = fill_template(data, replace)
    n = data.count('\n')
    data = data.replace('@LINES@', str(n + 1))

    # note that this replacement does not change the size of the header,
    # which would result into an inconsistency
    n = len(data) + getsize(tarball)
    data = data.replace('@SIZE_BYTES@', '%12d' % n)
    assert len(data) + getsize(tarball) == n

    return data


def create(info, verbose=False):
    tmp_dir = tempfile.mkdtemp()
    preconda_write_files(info, tmp_dir)

    preconda_tarball = join(tmp_dir, 'preconda.tar.bz2')
    p_t = tarfile.open(preconda_tarball, 'w:bz2')
    for dist in preconda_files:
        fn = filename_dist(dist)
        p_t.add(join(tmp_dir, fn), 'pkgs/' + fn)
    for key in 'pre_install', 'post_install':
        if key in info:
            p_t.add(info[key], 'pkgs/%s.sh' % key)
    cache_dir = join(tmp_dir, 'cache')
    if isdir(cache_dir):
        for cf in os.listdir(cache_dir):
            if cf.endswith(".json"):
                p_t.add(join(cache_dir, cf), 'pkgs/cache/' + cf)
    p_t.add(join(tmp_dir, 'conda-meta', 'history'), 'conda-meta/history')
    for dist in info['_dists']:
        _dist = filename_dist(dist)[:-8]
        record_file = join(_dist, 'info', 'repodata_record.json')
        record_file_src = join(tmp_dir, record_file)
        record_file_dest = join('pkgs', record_file)
        p_t.add(record_file_src, record_file_dest)
    p_t.close()

    tarball = join(tmp_dir, 'tmp.tar')
    t = tarfile.open(tarball, 'w')
    t.add(preconda_tarball, basename(preconda_tarball))
    if 'license_file' in info:
        t.add(info['license_file'], 'LICENSE.txt')
    for dist in info['_dists']:
        fn = filename_dist(dist)
        t.add(join(info['_download_dir'], fn), 'pkgs/' + fn)
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
