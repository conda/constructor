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
from conda.api import get_index
from conda.fetch import fetch_pkg
from conda.plan import add_defaults_to_specs
from conda.resolve import Resolve

from .utils import name_dist, dist2filename, url2dist

dists = []
urls = []
md5s = {}
r = None


def resolve(info):
    if not r:
        sys.exit("Error: index is empty, maybe 'channels' are missing?")
    specs = info['specs']
    add_defaults_to_specs(r, [], specs)
    res = r.solve(specs)

    if 'install_in_dependency_order' in info:
        sort_info = {name_dist(d): d[:-8] for d in res}
        dists.extend(d + '.tar.bz2' for d in r.graph_sort(sort_info))
    else:
        dists.extend(res)


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
        if url:
            fkey = url2dist(url + fn) + '.tar.bz2'
            if fkey not in r.index:
                sys.exit("Error: no package '%s' in %s" % (fn, url))
        else:
            group = [fkey for fkey, info in iteritems(r.index)
                     if info['fn'] == fn]
            if not group:
                sys.exit("Error: did not find '%s' in any channels" % fn)
            fkey = sorted(group, key=r.version_key, reverse=True)[0]
        dists.append(fkey)
        md5s[fkey] = md5


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
platform: %(_platform)s""" % info)
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

    for fkey in dists:
        fn = dist2filename(fkey)
        path = join(download_dir, fn)
        md5 = md5s.get(fkey)
        pkginfo = r.index[fkey]
        md5_src = pkginfo.get('md5')
        if md5 and md5 != md5_src:
            sys.exit("Error: MD5 sum for '%s' does not match in remote "
                     "repodata %s" % (fn, pkginfo['channel']))
        if isfile(path) and md5_file(path) == md5_src:
            continue
        print('fetching: %s' % fn)
        fetch_pkg(pkginfo, download_dir)


def main(info, verbose=True):
    if 'channels' in info:
        urls.extend(info['channels'])
    if 'packages' in info:
        for url, _, _ in parse_packages(info['packages']):
            if url and url not in urls:
                urls.append(url)

    if urls:
        global r
        index = get_index(urls, prepend=False, platform=info['_platform'])
        r = Resolve(index)

    if 'specs' in info:
        resolve(info)
    exclude_packages(info)
    if 'packages' in info:
        handle_packages(info)

    if not info.get('install_in_dependency_order'):
        dists.sort()
    move_python_first()

    if verbose:
        show(info)
    check_dists()
    fetch(info)

    info['_dists'] = list(map(dist2filename, dists))
