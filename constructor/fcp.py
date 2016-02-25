# (c) 2016 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.
"""
fcp (fetch conda packages) module
"""
from __future__ import print_function, division, absolute_import

import re
import os
import sys
from collections import defaultdict
from os.path import isdir, isfile, join

from conda.compat import iteritems
from conda.utils import md5_file
from conda.fetch import fetch_index, fetch_pkg
from conda.plan import add_defaults_to_specs
from conda.resolve import Resolve


dists = []
index = {}
urls = {}
md5s = {}


def resolve(info):
    specs = info['specs']
    r = Resolve(index)
    add_defaults_to_specs(r, [], specs)
    res = list(r.solve(specs))
    sys.stdout.write('\n')

    sort_info = {}
    for d in res:
        name, unused_version, unused_build = d.rsplit('-', 2)
        sort_info[name] = d.rsplit('.tar.bz2', 1)[0]

    res = map(lambda d: d + '.tar.bz2', r.graph_sort(sort_info))

    for dist in res:
        if dist.rsplit('-', 2)[0] == 'python':
            dists.insert(0, dist)
        else:
            dists.append(dist)


url_pat = re.compile(r'''
(?P<url>\S+/)?                    # optional URL
(?P<fn>[^\s#/]+)                  # filename
([#](?P<md5>[0-9a-f]{32}))?       # optional MD5
$                                 # EOL
''', re.VERBOSE)
def parse_packages(lines):
    for line in lines:
        line = line.strip()
        if not line or line.startswith(('#', '@')):
            continue
        m = url_pat.match(line)
        if m is None:
            sys.exit("Error: Could not parse: %s" % line)
        fn = m.group('fn')
        fn = fn.replace('=', '-')
        if not fn.endswith('.tar.bz2'):
            fn += '.tar.bz2'
        yield m.group('url'), fn, m.group('md5')


def handle_packages(info):
    for url, fn, md5 in parse_packages(info['packages']):
        dists.append(fn)
        md5s[fn] = md5
        if url:
            urls[fn] = url
        else:
            try:
                urls[fn] = index[fn]['channel']
            except KeyError:
                sys.exit("Error: did not find '%s' in any listed "
                         "channels" % fn)


def show(info):
    print("""
name: %(name)s
version: %(version)s
platform: %(platform)s
""" % info)
    for fn in dists:
        print('    %s' % fn)
    print()


def check_dists():
    if len(dists) == 0:
        sys.exit('Error: no packages specified')
    map_name = defaultdict(list) # map package name to list of filenames
    for i, fn in enumerate(dists):
        if not fn.endswith('.tar.bz2'):
            sys.exit("Error: '%s' does not end with '.tar.bz2'" % fn)
        dist = fn[:-8]
        try:
            name, version, build = dist.rsplit('-', 2)
        except ValueError:
            sys.exit("Error: Not a valid package filename: '%s'" % fn)

        map_name[name].append(fn)
        if i == 0 and name != 'python':
            sys.exit("Error: 'python' needs to be the first package specified")

    for name, files in iteritems(map_name):
        if len(files) > 1:
            sys.exit("Error: '%s' listed muptiple times: %s" %
                     (name, ', '.join(files)))


def fetch(info):
    download_dir = info['_download_dir']
    if not isdir(download_dir):
        os.makedirs(download_dir)

    for fn in dists:
        path = join(download_dir, fn)
        url = urls.get(fn)
        md5 = md5s.get(fn)
        if url:
            url_index = fetch_index((url,))
            try:
                pkginfo = url_index[fn]
            except KeyError:
                sys.exit("Error: no package '%s' in index" % fn)
        else:
            pkginfo = index[fn]

        if md5 and md5 != pkginfo['md5']:
            sys.exit("Error: MD5 sum for '%s' in %s does not match remote "
                     "index" % (fn, info.get('packages')))

        if isfile(path) and md5_file(path) == pkginfo['md5']:
            continue
        print('fetching: %s' % fn)
        fetch_pkg(pkginfo, download_dir)


def main(info, verbose=True):
    if 'channels' in info:
        global index
        index = fetch_index(
                      tuple('%s/%s/' % (url.rstrip('/'), info['platform'])
                            for url in info['channels']))

    if 'specs' in info:
        resolve(info)

    if 'packages' in info:
        handle_packages(info)

    if verbose:
        show(info)
    check_dists()
    fetch(info)

    info['_dists'] = dists
    info['_dist0'] = dists[0]
