# (c) 2016 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import re

import yaml

import conda.config



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


def parse(path):
    with open(path) as fi:
        data = fi.read()
    # try to get the platform from the construct data
    platform = yaml.load(data).get('platform', conda.config.subdir)
    # now that we know the platform, we filter lines by selectors (if any),
    # and get the final result
    info = yaml.load(select_lines(data, ns_platform(platform)))
    # ensure result includes 'platform' key
    info['platform'] = platform
    return info
