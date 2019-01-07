# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from __future__ import absolute_import, division, print_function

import os
from os.path import basename, dirname, getsize, join
import sys
import tarfile
import tempfile

from .construct import ns_platform
from .preconda import write_files as preconda_write_files
from .utils import add_condarc, fill_template, md5_file, preprocess, read_ascii_only

THIS_DIR = dirname(__file__)


def read_header_template():
    path = join(THIS_DIR, 'header.sh')
    print('Reading: %s' % path)
    with open(path) as fi:
        return fi.read()


def get_header(tarball, info):
    name = info['name']
    has_license = bool('license_file' in info)
    ppd = ns_platform(info['_platform'])
    ppd['attempt_hardlinks'] = bool(info.get('attempt_hardlinks'))
    ppd['has_license'] = has_license
    for key in 'pre_install', 'post_install':
        ppd['has_%s' % key] = bool(key in info)
    ppd['initialize_by_default'] = info.get('initialize_by_default', None)

    install_lines = add_condarc(info)
    # Needs to happen first -- can be templated
    replace = {
        'NAME': name,
        'name': name.lower(),
        'VERSION': info['version'],
        'PLAT': info['_platform'],
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
    print("Wrapping archive with shell script")
    with tempfile.TemporaryDirectory() as tmp_dir:
        preconda_write_files(info, tmp_dir)
        preconda_archive = os.path.join(os.path.dirname(info['_outpath']), 'installer.conda')
        tarball = join(tmp_dir, 'tmp.tar')
        t = tarfile.open(tarball, 'w')
        install_binary = os.path.join(sys.prefix, 'bin', 'constructor_install')
        t.add(install_binary, basename(install_binary))
        t.add(preconda_archive, basename(preconda_archive))
        if 'license_file' in info:
            t.add(info['license_file'], 'LICENSE.txt')
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
