# (c) 2016 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import os
from os.path import basename, dirname, join


files = 'urls', 'urls.txt', '.install.py'


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

    for fn in files:
        os.chmod(join(dst_dir, fn), 0o664)
