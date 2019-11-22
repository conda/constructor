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

from .utils import filename_dist, get_final_url

from . import __version__ as CONSTRUCTOR_VERSION
from .conda_interface import (
    CONDA_INTERFACE_VERSION, Dist, MatchSpec, default_prefix, PrefixData, write_repodata, get_repodata
)

try:
    import json
except:
    import ruamel_json as json

files = '.constructor-build.info', 'urls', 'urls.txt', 'env.txt'


def write_index_cache(info, dst_dir, used_packages):
    cache_dir = join(dst_dir, 'cache')

    if not isdir(cache_dir):
        os.makedirs(cache_dir)

    _platforms = info['_platform'], 'noarch'
    _remaps = {url['src'].rstrip('/'): url['dest'].rstrip('/')
               for url in info.get('channels_remap', [])}
    _urls = set(url.rstrip('/') for url in list(_remaps) +
                info.get('channels', []) +
                info.get('conda_default_channels', []))
    subdir_urls = tuple('%s/%s/' % (url, subdir)
                        for url in _urls for subdir in _platforms)
    repodatas = {url: get_repodata(url) for url in subdir_urls}

    for url, _ in info['_urls']:
        src, subdir, fn = url.rsplit('/', 2)
        dst = _remaps.get(src)
        if dst is not None:
            src = '%s/%s/' % (src, subdir)
            dst = '%s/%s/' % (dst, subdir)
            if dst not in repodatas:
                repodatas[dst] =  {
                    '_url': dst,
                    'info': {'subdir': subdir},
                    'packages': {},
                    'packages.conda': {},
                    'removed': []
                }
            loc = 'packages.conda' if fn.endswith('.conda') else 'packages'
            repodatas[dst][loc][fn] = repodatas[src][loc][fn]
    for src in _remaps:
        for subdir in _platforms:
            del repodatas['%s/%s/' % (src, subdir)]

    for url, repodata in repodatas.items():
        write_repodata(cache_dir, url, repodata, used_packages)

    for cache_file in os.listdir(cache_dir):
        if not cache_file.endswith(".json"):
            os.unlink(join(cache_dir, cache_file))


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

    write_index_cache(info, dst_dir, info['_dists'])

    write_conda_meta(info, dst_dir, final_urls_md5s)

    write_repodata_record(info, dst_dir)

    write_env_txt(info, dst_dir)

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
        if filename_dist(dist).endswith(".conda"):
            _dist = filename_dist(dist)[:-6]
        elif filename_dist(dist).endswith(".tar.bz2"):
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


def write_env_txt(info, dst_dir):
    dists_san_extn = []
    for dist in info['_dists']:
        if filename_dist(dist).endswith('.conda'):
            dists_san_extn.append(filename_dist(dist)[:-6])
        elif filename_dist(dist).endswith('.tar.bz2'):
            dists_san_extn.append(filename_dist(dist)[:-8])
    specs = ['='.join(spec.rsplit('-', 2)) for spec in dists_san_extn]
    with open(join(dst_dir, "env.txt"), "w") as envf:
        envf.write('\n'.join(specs))
