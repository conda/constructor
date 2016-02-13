# (c) 2016 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from __future__ import print_function, division, absolute_import

import os
import re
import sys
from os.path import isdir, isfile, join

import yaml

import conda.config
from conda.utils import md5_file
from conda.fetch import fetch_index, fetch_pkg
from conda.plan import add_defaults_to_specs
from conda.resolve import Resolve


DISTS = None
INDEX = None
REPO_DIR = None


def ns_platform(platform):
    return dict(
        linux = platform.startswith('linux-'),
        linux32 = bool(platform == 'linux-32'),
        linux64 = bool(platform == 'linux-64'),
        armv7l = bool(platform == 'linux-armv7l'),
        ppc64le = bool(platform == 'linux-ppc64le'),
        osx = platform.startswith('osx-'),
        win = platform.startswith('win-'),
        win32 = bool(platform == 'win-32'),
        win64 = bool(platform == 'win-64'),
    )


sel_pat = re.compile(r'(.+?)\s*\[(.+)\]$')
def select_lines(data, namespace):
    lines = []
    for line in data.splitlines():
        line = line.rstrip()
        m = sel_pat.match(line)
        if m:
            cond = m.group(2)
            if eval(cond, namespace, {}):
                lines.append(m.group(1))
            continue
        lines.append(line)
    return '\n'.join(lines) + '\n'


def parse_info(path):
    with open(path) as fi:
        data = fi.read()
    platform = yaml.load(data).get('platform', conda.config.subdir)
    info = yaml.load(select_lines(data, ns_platform(platform)))
    info['platform'] = platform
    return info


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
