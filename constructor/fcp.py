# (c) 2016 Anaconda, Inc. / https://anaconda.com
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
from os.path import isdir, isfile, join, getsize
import re
import sys
import tarfile

from .conda_interface import (NoPackagesFound, Resolve, fetch_index, fetch_pkg,
                              MatchSpec)
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
    if not any(MatchSpec(s).name == 'python' for s in specs):
        specs.append('python')
    if verbose:
        print("specs: %r" % specs)

    try:
        res = list(r.solve(specs))
    except NoPackagesFound as e:
        sys.exit("Error: %s" % e)
    sys.stdout.write('\n')

    if 'install_in_dependency_order' in info:
        sort_info = {name_dist(d): d for d in res}
        dists.extend(d for d in r.dependency_sort(sort_info))
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

# nsis and pkg installers automatically compute the tarballs size
# so this might not really be needed for them
def update_approx_tarballs_size(info, size):
    if '_approx_tarballs_size' not in info:
        # Keep a min, 50MB buffer size
        info['_approx_tarballs_size'] = 52428800
    info['_approx_tarballs_size'] += size

# for computing the size of the contents of all the tarballs in bytes
def update_approx_pkgs_size(info, size):
    if '_approx_pkgs_size' not in info:
        # Keep a min, 50MB buffer size
        info['_approx_pkgs_size'] = 52428800
    info['_approx_pkgs_size'] += size

def check_duplicates_files(info):
    print('Checking for duplicate files ...')

    map_members_scase = defaultdict(set)
    map_members_icase = {}

    for dist in info['_dists']:
        fn = filename_dist(dist)
        fn_path = join(info['_download_dir'], fn)
        t = tarfile.open(fn_path)
        update_approx_tarballs_size(info, os.path.getsize(fn_path))
        for member in t.getmembers():
            update_approx_pkgs_size(info, member.size)
            if member.type == tarfile.DIRTYPE:
                continue
            mname = member.name
            if not mname.split('/')[0] in ['info', 'recipe']:
                map_members_scase[mname].add(fn)
                key = mname.lower()
                if key not in map_members_icase:
                    map_members_icase[key] = {'files':set(), 'fns':set()}
                map_members_icase[key]['files'].add(mname)
                map_members_icase[key]['fns'].add(fn)
        t.close()

    for member in map_members_scase:
        fns = map_members_scase[member]
        msg_str = "File '%s' found in multiple packages: %s" % (
                  member, ', '.join(fns))
        if len(fns) > 1:
            if info.get('ignore_duplicate_files'):
                print('Warning: {}'.format(msg_str))
            else:
                sys.exit('Error: {}'.format(msg_str))

    for member in map_members_icase:
        # Some filesystems are not case sensitive by default (e.g HFS)
        # Throw warning on linux and error out on macOS/windows
        fns = map_members_icase[member]['fns']
        files = list(map_members_icase[member]['files'])
        msg_str = "Files %s found in the package(s): %s" % (
                   str(files)[1:-1], ', '.join(fns))
        if len(files) > 1:
            if (info.get('ignore_duplicate_files') or
                info['_platform'].startswith('linux')):
                print('Warning: {}'.format(msg_str))
            else:
                sys.exit('Error: {}'.format(msg_str))


def main(info, verbose=True, dry_run=False):
    if 'channels' in info:
        global index

        _platforms = info['_platform'], 'noarch'
        _urls = info['channels']
        _urls = _urls + [x['src'] for x in info.get('channels_remap', [])]
        subdir_urls = tuple('%s/%s/' % (url.rstrip('/'), subdir)
                            for url in _urls for subdir in _platforms)
        index = fetch_index(subdir_urls)

    if 'specs' in info:
        resolve(info, verbose)
    exclude_packages(info)

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

    check_duplicates_files(info)
