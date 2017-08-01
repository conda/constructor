# (c) 2016 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.
"""
fcp (fetch conda packages) module
"""
from __future__ import absolute_import, division, print_function

from collections import defaultdict
import os
from os.path import isdir, isfile, join
import re
import sys

from .conda_interface import NoPackagesFound, Resolve, fetch_index, fetch_pkg
from .install import name_dist
from .utils import filename_dist, md5_file

dists = []
index = {}
urls = {}
md5s = {}


def resolve(info, verbose=False):
    if not index:
        sys.exit("Error: index is empty, maybe 'channels' are missing?")
    specs = info['specs']
    r = Resolve(index)
    if not any(s.split()[0] == 'python' for s in specs):
        specs.append('python')
    if verbose:
        print("specs: %r" % specs)

    try:
        res = list(r.solve(specs))
    except NoPackagesFound as e:
        sys.exit("Error: %s" % e)
    sys.stdout.write('\n')

    if 'install_in_dependency_order' in info:
        sort_info = {name_dist(d): d[:-8] for d in res}
        dists.extend(d + '.tar.bz2' for d in r.graph_sort(sort_info))
    else:
        dists.extend(res)


def check_duplicates():
    map_name = defaultdict(list) # map package name to list of filenames
    for fn in dists:
        map_name[name_dist(fn)].append(fn)

    for name, files in map_name.items():
        if len(files) > 1:
            sys.exit("Error: '%s' listed multiple times: %s" %
                     (name, ', '.join(files)))


def exclude_packages(info):
    check_duplicates()
    for name in info.get('exclude', []):
        for bad_char in ' =<>*':
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
cache download location: %(_download_dir)s
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
    # always use the libconda fetch_index function here since no
    # channel priority is needed
    download_dir = info['_download_dir']
    if not isdir(download_dir):
        os.makedirs(download_dir)

    info['_urls'] = []
    for dist in dists:
        fn = filename_dist(dist)
        path = join(download_dir, fn)
        url = urls.get(dist)
        md5 = md5s.get(dist)
        if url:
            url_index = fetch_index((url,))
            try:
                pkginfo = url_index[dist]
            except KeyError:
                sys.exit("Error: no package '%s' in %s" % (dist, url))
        else:
            pkginfo = index[dist]

        # convert pkginfo to flat dict
        try:
            pkginfo = pkginfo.dump()
        except AttributeError:
            # pkginfo was already a dict
            pass

        if not pkginfo['channel'].endswith('/'):
            pkginfo['channel'] += '/'
        assert pkginfo['channel'].endswith('/')
        info['_urls'].append((pkginfo['channel'] + fn, pkginfo['md5']))

        if md5 and md5 != pkginfo['md5']:
            sys.exit("Error: MD5 sum for '%s' does not match in remote "
                     "repodata %s" % (fn, url))

        if isfile(path) and md5_file(path) == pkginfo['md5']:
            continue
        print('fetching: %s' % fn)
        fetch_pkg(pkginfo, download_dir)


def main(info, verbose=True, dry_run=False):
    if 'channels' in info:
        global index

        _platforms = info['_platform'], 'noarch'
        _urls = info['channels']
        subdir_urls = tuple('%s/%s/' % (url.rstrip('/'), subdir)
                            for url in _urls for subdir in _platforms)
        index = fetch_index(subdir_urls)

    if 'specs' in info:
        resolve(info, verbose)
    exclude_packages(info)
    if 'packages' in info:
        handle_packages(info)

    if not info.get('install_in_dependency_order'):
        dists.sort()
    move_python_first()

    all_names = set(name_dist(fn) for fn in dists)
    for name in info.get('menu_packages', []):
        if name not in all_names:
            print("WARNING: no such package (in menu_packages): %s" % name)

    if verbose:
        show(info)
    check_dists()
    if dry_run:
        return
    fetch(info)

    info['_dists'] = list(dists)
