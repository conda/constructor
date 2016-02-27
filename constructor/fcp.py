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

from constructor.utils import name_dist


dists = []
index = {}
urls = {}
md5s = {}


def resolve(info):
    if not index:
        sys.exit("Error: index is empty, maybe 'channels' are missing?")
    specs = info['specs']
    r = Resolve(index)
    add_defaults_to_specs(r, [], specs)
    res = list(r.solve(specs))
    sys.stdout.write('\n')

    sort_info = {name_dist(d): d[:-8] for d in res}
    dists.extend(d + '.tar.bz2' for d in r.graph_sort(sort_info))


def check_duplicates():
    map_name = defaultdict(list) # map package name to list of filenames
    for fn in dists:
        map_name[name_dist(fn)].append(fn)

    for name, files in iteritems(map_name):
        if len(files) > 1:
            sys.exit("Error: '%s' listed multiple times: %s" %
                     (name, ', '.join(files)))


def exclude_packages(info):
    check_duplicates()
    for name in info.get('exclude', []):
        for bad_char in '- =<>*':
            if bad_char in name:
                sys.exit("Error: did not expect '%s' in package name: %s" %
                         name)
        # find the package with name, and remove it
        for dist in list(dists):
            if name_dist(dist) == name:
                dists.remove(dist)
                break
        else:
            sys.exit("Error: no package named '%s' to remove" % name)


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
        if fn.count('-') < 2:
            sys.exit("Error: Not a valid conda package filename: '%s'" % fn)
        dists.append(fn)
        md5s[fn] = md5
        if url:
            urls[fn] = url
        else:
            try:
                urls[fn] = index[fn]['channel']
            except KeyError:
                sys.exit("Error: did not find '%s' in any channels" % fn)


def move_python_first():
    for dist in list(dists):
        if name_dist(dist) == 'python':
            dists.remove(dist)
            dists.insert(0, dist)
            return


def show(info):
    print("""
name: %(name)s
version: %(version)s
platform: %(platform)s""" % info)
    print("number of package: %d" % len(dists))
    for fn in dists:
        print('    %s' % fn)
    print()


def check_dists():
    if len(dists) == 0:
        sys.exit('Error: no packages specified')
    check_duplicates()
    assert name_dist(dists[0]) == 'python'


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
                sys.exit("Error: no package '%s' in %s" % (fn, url))
        else:
            pkginfo = index[fn]

        if md5 and md5 != pkginfo['md5']:
            sys.exit("Error: MD5 sum for '%s' does not match in remote "
                     "repodata %s" % (fn, url))

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
    exclude_packages(info)
    if 'packages' in info:
        handle_packages(info)

    if info.get('sort_by_name'):
        dists.sort()
    move_python_first()

    if verbose:
        show(info)
    check_dists()
    fetch(info)

    info['_dists'] = list(dists)
