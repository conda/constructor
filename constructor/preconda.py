# (c) 2016 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import os
from os.path import basename, dirname, join, isdir

# This should ideally be from conda.exports
from conda.core.repodata import fetch_repodata

files = 'urls', 'urls.txt', '.install.py'

def write_index_cache(info, dst_dir):
    global files
    cache_dir = join(dst_dir, 'cache')

    if not isdir(cache_dir):
        os.makedirs(cache_dir)

    _platforms = info['_platform'], 'noarch'
    _urls = set(info['channels'] + info['conda_default_channels'])
    subdir_urls = tuple('%s/%s/' % (url.rstrip('/'), subdir)
		    for url in _urls for subdir in _platforms)

    for url in subdir_urls:
        # print('Adding repodata for %s ...'%url)
        fetch_repodata(url, None, 0,
	   cache_dir=cache_dir, use_cache=False, session=None)

    for cache_file in os.listdir(cache_dir):
        files += join(cache_dir, cache_file),

def create_install(info, dst_dir):
    with open(join(dirname(__file__), 'install.py')) as fi:
        data = fi.read()

    iplace = "#meta['installed_by'] = ..."
    icode = "meta['installed_by'] = '%s'" % basename(info['_outpath'])
    assert data.count(iplace) == 1
    data = data.replace(iplace, icode)

    with open(join(dst_dir, '.install.py'), 'w') as fo:
        fo.write(data)


def write_files(info, dst_dir):
    with open(join(dst_dir, 'urls'), 'w') as fo:
        for url, md5 in info['_urls']:
            fo.write('%s#%s\n' % (url, md5))

    with open(join(dst_dir, 'urls.txt'), 'w') as fo:
        for url, unused_md5 in info['_urls']:
            fo.write('%s\n' % url)

    create_install(info, dst_dir)

    write_index_cache(info, dst_dir)

    for fn in files:
        os.chmod(join(dst_dir, fn), 0o664)
