from __future__ import print_function, division, absolute_import

import os
import sys
from os.path import isdir, isfile, join

from conda.utils import md5_file
from conda.fetch import fetch_index, fetch_pkg
from conda.plan import add_defaults_to_specs
from conda.resolve import Resolve


DISTS = None
INDEX = None
REPO_DIR = None


def ns_info(info):
    subdir = info['platform']
    return dict(
        linux = subdir.startswith('linux-'),
        linux32 = bool(subdir == 'linux-32'),
        linux64 = bool(subdir == 'linux-64'),
        armv7l = bool(subdir == 'linux-armv7l'),
        ppc64le = bool(subdir == 'linux-ppc64le'),
        osx = subdir.startswith('osx-'),
        win = subdir.startswith('win-'),
        win32 = bool(subdir == 'win-32'),
        win64 = bool(subdir == 'win-64'),
    )


def set_index(info):
    global INDEX

    INDEX = fetch_index(tuple('%s/%s/' % (url.rstrip('/'), info['platform'])
                              for url in info['channels']))


def resolve(info):
    """
    sets global DISTS and INDEX
    """
    global DISTS

    specs = info['specs']
    r = Resolve(INDEX)
    add_defaults_to_specs(r, [], specs)
    DISTS = list(r.solve(specs))

    sort_info = {}
    for d in DISTS:
        name, unused_version, unused_build = d.rsplit('-', 2)
        sort_info[name] = d.rsplit('.tar.bz2', 1)[0]

    DISTS = map(lambda d: d + '.tar.bz2', r.graph_sort(sort_info))


def move_python_first():
    global DISTS

    res = []
    for dist in DISTS:
        if dist.rsplit('-', 2)[0] == 'python':
            res.insert(0, dist)
        else:
            res.append(dist)
    DISTS = res


def show(info):
    print("""
name: %(name)s
version: %(version)s
platform: %(platform)s
""" % info)
    for fn in DISTS:
        print('    %s' % fn)


def check_dists():
    if len(DISTS) == 0:
        sys.exit('Error: no packages specified')
    for i, fn in enumerate(DISTS):
        if not fn.endswith('.tar.bz2'):
            sys.exit("Error: '%s' does not end with '.tar.bz2'" % fn)
        dist = fn[:-8]
        try:
            name, version, build = dist.rsplit('-', 2)
        except ValueError:
            sys.exit("Error: Not a valid package filename: '%s'" % fn)
        if i == 0 and name != 'python':
            sys.exit("Error: 'python' needs to be the first package specified")


def fetch(info):
    global REPO_DIR

    REPO_DIR = join(os.getenv('HOME'), '.conda/constructor',
                    info['platform'])
    if not isdir(REPO_DIR):
        os.makedirs(REPO_DIR)
    for fn in DISTS:
        path = join(REPO_DIR, fn)
        if isfile(path) and md5_file(path) == INDEX[fn]['md5']:
            continue
        print('fetching: %s' % fn)
        fetch_pkg(INDEX[fn], REPO_DIR)
