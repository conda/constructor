# (c) 2016 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import os
from os.path import basename, dirname, join, isdir

# This should ideally be from conda.exports
from conda.core.repodata import fetch_repodata

try:
    import json
except:
    import ruamel_json as json

files = 'system.info', 'urls', 'urls.txt', '.install.py'

def write_index_cache(info, dst_dir):
    global files
    cache_dir = join(dst_dir, 'cache')

    if not isdir(cache_dir):
        os.makedirs(cache_dir)

    _platforms = info['_platform'], 'noarch'
    _urls = set(info.get('channels', []) +
                info.get('conda_default_channels', []))
    subdir_urls = tuple('%s/%s/' % (url.rstrip('/'), subdir) for url in _urls
            if not url.startswith('file://') for subdir in _platforms)

    for url in subdir_urls:
        # print('Adding repodata for %s ...'%url)
        fetch_repodata(url, None, 0, cache_dir=cache_dir,
                       use_cache=False, session=None)

    for cache_file in os.listdir(cache_dir):
        if cache_file.endswith(".json"):
            files += join(cache_dir, cache_file),
        else:
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
                fn='%s.tar.bz2' % dist
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
            print("WARNING: You need to make the package {} available "
                  "at {}".format(url.rsplit('/', 1)[1], new_url))
            return new_url
    return url


def system_info():
    import constructor, conda, sys
    return {'constructor': constructor.__version__,
            'conda': conda.__version__,
            'platform': sys.platform,
            'python': sys.version,
            'python_version': tuple(sys.version_info)}


def write_files(info, dst_dir):
    with open(join(dst_dir, 'system.info'), 'w') as fo:
        json.dump(system_info(), fo)

    with open(join(dst_dir, 'urls'), 'w') as fo:
        for url, md5 in info['_urls']:
            fo.write('%s#%s\n' % (get_final_url(info, url), md5))

    with open(join(dst_dir, 'urls.txt'), 'w') as fo:
        for url, unused_md5 in info['_urls']:
            fo.write('%s\n' % get_final_url(info, url))

    create_install(info, dst_dir)

    write_index_cache(info, dst_dir)

    for fn in files:
        os.chmod(join(dst_dir, fn), 0o664)
