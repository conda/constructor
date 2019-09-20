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
from .utils import add_condarc, filename_dist, fill_template, md5_files, preprocess, read_ascii_only, get_final_channels

THIS_DIR = dirname(__file__)


def read_header_template():
    path = join(THIS_DIR, 'header.sh')
    print('Reading: %s' % path)
    with open(path) as fi:
        return fi.read()


def get_header(conda_exec, tarball, info):
    name = info['name']

    has_license = bool('license_file' in info)
    ppd = ns_platform(info['_platform'])
    ppd['keep_pkgs'] = bool(info.get('keep_pkgs'))
    ppd['attempt_hardlinks'] = bool(info.get('attempt_hardlinks'))
    ppd['has_license'] = has_license
    for key in 'pre_install', 'post_install', 'pre_uninstall':
        ppd['has_%s' % key] = bool(key in info)
    ppd['initialize_by_default'] = info.get('initialize_by_default', None)
    install_lines = list(add_condarc(info))
    # Needs to happen first -- can be templated
    replace = {
        'NAME': name,
        'name': name.lower(),
        'VERSION': info['version'],
        'PLAT': info['_platform'],
        'DEFAULT_PREFIX': info.get('default_prefix',
                                   '$HOME/%s' % name.lower()),
        'MD5': md5_files([conda_exec, tarball]),
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
    data = data.replace('@CHANNELS@', ','.join(get_final_channels(info)))

    # Make all replacements before this - nothing beyond here is allowed to change the size of the header.
    #    If the header size changes, the offsets for extracting things will be wrong and nothing will work.

    # block size for dd in bytes
    block_size = 16 * 1024
    total_size = len(data) + getsize(conda_exec) + getsize(tarball)
    # NOTE: strings here need to be the same length for sake of replacement length being same
    whitespace = 0
    def replace_and_add_to_whitespace(data, string, value):
        value = str(value)
        whitespace = len(string) - len(value)
        data = data.replace(string, str(value) + (' ' * whitespace))
        return data

    for thing, string, extra_skip in ((conda_exec, 'CON_EXE', 0), (tarball, 'TARBALL', getsize(conda_exec))):
        start = len(data) + extra_skip
        # 3-part dd to handle block size alignment: https://unix.stackexchange.com/a/121798/34459
        thing_size = getsize(thing)
        copy1_size = block_size - (start % block_size)
        # zero padding is to ensure size of header doesn't change depending on
        #    size of packages included.  The actual space you have is the number
        #    of characters in the string here - @NON_PAYLOAD_SIZE@ is 18 chars
        data = replace_and_add_to_whitespace(data, '@%s_OFFSET_BYTES@' % string, str(start))
        data = replace_and_add_to_whitespace(data, '@%s_SIZE_BYTES@' % string, str(thing_size))
        data = replace_and_add_to_whitespace(data, '@%s_START_REMAINDER@' % string, str(copy1_size))
        copy2_start = start + copy1_size
        copy2_skip = copy2_start // block_size
        data = replace_and_add_to_whitespace(data, '@%s_BLOCK_OFFSET@' % string, str(copy2_skip))
        copy2_blocks = (thing_size - copy2_start + start) // block_size
        data = replace_and_add_to_whitespace(data, '@%s_SIZE_BLOCKS@' % string, str(copy2_blocks))
        copy3_start= (copy2_skip + copy2_blocks) * block_size
        data = replace_and_add_to_whitespace(data, '@%s_REMAINDER_OFFSET@' % string, str(copy3_start))
        copy3_size = thing_size - copy1_size - (copy2_blocks * block_size)
        data = replace_and_add_to_whitespace(data, '@%s_END_REMAINDER@' % string, str(copy3_size))

    data = replace_and_add_to_whitespace(data, '@BLOCK_SIZE@', str(block_size))
    # this one is not zero-padded because it is used in a different way, and is compared
    #    with the actual size at install time (which is not zero padded)
    data = data.replace('@TOTAL_SIZE_BYTES@', str(n))

    # assert that the total length of the file hasn't changed because of our string replacement
    assert len(data) + getsize(conda_exec) + getsize(tarball) == total_size, "Mismatch data length.  Before string format: %s; after: %s" % (total_size, len(data) + getsize(conda_exec) + getsize(tarball))

    return data


def create(info, verbose=False):
    tmp_dir = tempfile.mkdtemp()
    preconda_write_files(info, tmp_dir)

    preconda_tarball = join(tmp_dir, 'preconda.tar.bz2')
    postconda_tarball = join(tmp_dir, 'postconda.tar.bz2')
    pre_t = tarfile.open(preconda_tarball, 'w:bz2')
    post_t = tarfile.open(postconda_tarball, 'w:bz2')
    for dist in preconda_files:
        fn = filename_dist(dist)
        pre_t.add(join(tmp_dir, fn), 'pkgs/' + fn)
    for key in 'pre_install', 'post_install':
        if key in info:
            pre_t.add(info[key], 'pkgs/%s.sh' % key)
    cache_dir = join(tmp_dir, 'cache')
    if isdir(cache_dir):
        for cf in os.listdir(cache_dir):
            if cf.endswith(".json"):
                pre_t.add(join(cache_dir, cf), 'pkgs/cache/' + cf)
    for dist in info['_dists']:
        if filename_dist(dist).endswith(".conda"):
            _dist = filename_dist(dist)[:-6]
        elif filename_dist(dist).endswith(".tar.bz2"):
            _dist = filename_dist(dist)[:-8]
        record_file = join(_dist, 'info', 'repodata_record.json')
        record_file_src = join(tmp_dir, record_file)
        record_file_dest = join('pkgs', record_file)
        pre_t.add(record_file_src, record_file_dest)
    pre_t.addfile(tarinfo=tarfile.TarInfo("conda-meta/history"))
    post_t.add(join(tmp_dir, 'conda-meta', 'history'), 'conda-meta/history')
    pre_t.close()
    post_t.close()

    tarball = join(tmp_dir, 'tmp.tar')
    t = tarfile.open(tarball, 'w')
    t.add(preconda_tarball, basename(preconda_tarball))
    t.add(postconda_tarball, basename(postconda_tarball))
    if 'license_file' in info:
        t.add(info['license_file'], 'LICENSE.txt')
    for dist in info['_dists']:
        fn = filename_dist(dist)
        t.add(join(info['_download_dir'], fn), 'pkgs/' + fn)
    t.close()

    conda_exec = info["_conda_exe"]
    header = get_header(conda_exec, tarball, info)
    shar_path = info['_outpath']
    with open(shar_path, 'wb') as fo:
        fo.write(header.encode('utf-8'))
        for payload in [conda_exec, tarball]:
            with open(payload, 'rb') as fi:
                while True:
                    chunk = fi.read(262144)
                    if not chunk:
                        break
                    fo.write(chunk)

    os.unlink(tarball)
    os.chmod(shar_path, 0o755)
    shutil.rmtree(tmp_dir)
