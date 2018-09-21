# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import os
from os.path import basename, dirname, isdir, join, split as path_split
import platform
import sys
import time

from .utils import filename_dist

from . import __version__ as CONSTRUCTOR_VERSION
from .conda_interface import (
    CONDA_INTERFACE_VERSION, Dist, MatchSpec, default_prefix, PrefixData, write_repodata,
)

try:
    import json
except:
    import ruamel_json as json

files = '.constructor-build.info', 'urls', 'urls.txt', '.install.py'

def write_index_cache(info, dst_dir):
    cache_dir = join(dst_dir, 'cache')

    if not isdir(cache_dir):
        os.makedirs(cache_dir)

    _platforms = info['_platform'], 'noarch'
    _urls = set(info.get('channels', []) +
                info.get('conda_default_channels', []))
    subdir_urls = tuple('%s/%s/' % (url.rstrip('/'), subdir) for url in _urls
            if not url.startswith('file://') for subdir in _platforms)

    for url in subdir_urls:
        write_repodata(cache_dir, url)

    for cache_file in os.listdir(cache_dir):
        if not cache_file.endswith(".json"):
            os.unlink(join(cache_dir, cache_file))

def create_install(info, dst_dir):
    with open(join(dirname(__file__), 'install.py')) as fi:
        data = fi.read()

    replacements = [("#meta['installed_by'] = ...",
                     "meta['installed_by'] = '%s'" % basename(info['_outpath']))]
    if info['installer_type'] != 'sh':
        IDISTS = {}
        CENVS = {'root': []}
        for _dist in info['_dists']:
            if hasattr(_dist, 'fn'):
                dist = _dist.name
                fn = _dist.fn
                dist_name = _dist.dist_name
            else:
                dist_name = _dist
                if _dist.endswith(".tar.bz2"):
                  dist_name = _dist[:-8]
                fn = '%s.tar.bz2' % dist_name
            # Find the URL for this fn.
            for url, md5 in info['_urls']:
                if url.rsplit('/', 1)[1] == fn:
                    break
            IDISTS[dist_name] = {'url': get_final_url(info, url),
                            'md5': md5}
            CENVS['root'].append(dist_name)
        replacements.append(('IDISTS = {}',
                             'IDISTS = %s\n' % json.dumps(IDISTS, indent=2, sort_keys=True) +
                             'C_ENVS = %s\n' % json.dumps(CENVS, indent=2, sort_keys=True)))
    for iplace, icode in replacements:
        assert data.count(iplace) == 1
        data = data.replace(iplace, icode)

    with open(join(dst_dir, '.install.py'), 'w') as fo:
        fo.write(data)

def get_final_url(info, url):
    mapping = info.get('channels_remap', [])
    for entry in mapping:
        src = entry['src']
        dst = entry['dest']
        if url.startswith(src):
            new_url = url.replace(src, dst)
            if url.endswith(".tar.bz2"):
              print("WARNING: You need to make the package {} available "
                    "at {}".format(url.rsplit('/', 1)[1], new_url))
            return new_url
    return url


def system_info():
    out = {'constructor': CONSTRUCTOR_VERSION,
           'conda': CONDA_INTERFACE_VERSION,
           'platform': sys.platform,
           'python': sys.version,
           'python_version': tuple(sys.version_info),
           'machine': platform.machine(),
           'platform_full': platform.version()}
    if sys.platform == 'darwin':
        out['extra'] = platform.mac_ver()
    elif sys.platform.startswith('linux'):
        out['extra'] = platform.dist()
    elif sys.platform.startswith('win'):
        out['extra'] = platform.win32_ver()
        prefix = default_prefix
        prefix_records = list(PrefixData(prefix).iter_records())
        nsis_prefix_rec = next(
            (rec for rec in prefix_records if rec.name == 'nsis'), None)
        if nsis_prefix_rec:
            out['nsis'] = nsis_prefix_rec.version
    return out


def write_files(info, dst_dir):
    with open(join(dst_dir, '.constructor-build.info'), 'w') as fo:
        json.dump(system_info(), fo)

    final_urls_md5s = tuple((get_final_url(info, url), md5) for url, md5 in info['_urls'])

    with open(join(dst_dir, 'urls'), 'w') as fo:
        for url, md5 in final_urls_md5s:
            fo.write('%s#%s\n' % (url, md5))

    with open(join(dst_dir, 'urls.txt'), 'w') as fo:
        for url, _ in final_urls_md5s:
            fo.write('%s\n' % url)

    create_install(info, dst_dir)

    write_index_cache(info, dst_dir)

    write_conda_meta(info, dst_dir, final_urls_md5s)

    write_repodata_record(info, dst_dir)

    for fn in files:
        os.chmod(join(dst_dir, fn), 0o664)


def write_conda_meta(info, dst_dir, final_urls_md5s):
    user_requested_specs = info.get('user_requested_specs', info['specs'])
    cmd = path_split(sys.argv[0])[-1]
    if len(sys.argv) > 1:
        cmd = "%s %s" % (cmd, " ".join(sys.argv[1:]))

    builder = [
        "==> %s <==" % time.strftime('%Y-%m-%d %H:%M:%S'),
        "# cmd: %s" % cmd,
    ]
    dists = tuple(Dist(url) for url, _ in final_urls_md5s)

    builder.extend("+%s" % dist.full_name for dist in dists)
    if user_requested_specs:
        update_specs = [str(MatchSpec(s)) for s in user_requested_specs]
        builder.append("# update specs: %s" % update_specs)
    builder.append("\n")

    if not isdir(join(dst_dir, 'conda-meta')):
        os.makedirs(join(dst_dir, 'conda-meta'))
    with open(join(dst_dir, 'conda-meta', 'history'), 'w') as fh:
        fh.write("\n".join(builder))

def write_repodata_record(info, dst_dir):
    for dist in info['_dists']:
        _dist = filename_dist(dist)[:-8]
        record_file = join(_dist, 'info', 'repodata_record.json')
        record_file_src = join(info['_download_dir'], record_file)

        with open(record_file_src, 'r') as rf:
          rr_json = json.load(rf)

        rr_json['url'] = get_final_url(info, rr_json['url'])
        rr_json['channel'] = get_final_url(info, rr_json['channel'])

        if not isdir(join(dst_dir, _dist, 'info')):
          os.makedirs(join(dst_dir, _dist, 'info'))

        record_file_dest = join(dst_dir, record_file)

        with open(record_file_dest, 'w') as rf:
          json.dump(rr_json, rf, indent=2, sort_keys=True)
