# (c) 2016 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import re
import sys

import yaml

import conda.config


# list of tuples (key name, required, type, description)
KEYS = [
    ('name',                   True,  str, '''
Name of the installer.  May also contain uppercase letter.  The installer
name is independent of the names of any of the conda packages the installer
is composed of.
'''),

    ('version',                True,  str, '''
Version of the installer.  Just like the installer name, this version
is independent of any conda package versions contained in the installer.
'''),

    ('channels',               False, list, '''
The conda channels from which packages are retrieved, when using the `specs`
key below, but also when using the `packages` key ,unless the full URL is
given in the `packages` list (see below).
'''),

    ('specs',                  False, (list, str), '''
List of package specifications, e.g. `python 2.7*`, `pyzmq` or `numpy >=1.8`.
This list of specifications if given to the conda resolver (as if you were
to create a new environment with those specs.
'''),

    ('exclude',                False, list, '''
List of package names to be excluded, after the '`specs` have been resolved.
For example, you can say that `readline` should be excluded, even though it
is contained as a result of resolving the specs for `python 2.7`.
'''),

    ('packages',               False, (list, str), '''
A list of explicit conda packages to be included, eg. `yaml-0.1.6-0.tar.bz2`.
The packages may also be specified by their entire URL,
eg.`https://repo.continuum.io/pkgs/free/osx-64/openssl-1.0.1k-1.tar.bz2`.
Optionaly, the MD5 hash sum of the package, may be added after an immediate
`#` character, eg. `readline-6.2-2.tar.bz2#0801e644bd0c1cd7f0923b56c52eb7f7`.
'''),

    ('sort_by_name',           False, bool, '''
By default packages are sorted by install dependency order (unless the
explicit list in `packages` is used.  Python is always moved to the front
of the packages to be installed.  This option allows sorting by the package
names instead.
'''),

    ('platform',               False, str, '''
The platform for which the installer is created, eg. `linux-32`.  This is
not necessarily the current platform.  The default, however, is the current
platform.
'''),

    ('conda_default_channels', False, list, 'XXX'),

    ('installer_filename',     False, str, '''
The filename of the installer being created.  A reasonable default filename
will determined by the `name`, `version`, `platform` and installer type.
'''),

    ('license_file',           False, str, '''
Path to the license file being displayed by the installer during the install
process.
'''),

    ('default_prefix',         False, str, 'XXX'),

    ('welcome_image',          False, str, '''
Path to an image which is used as the welcome image for the Windows
installer.  The image is resized to 164 x 314 pixels.
By default, an image is automatically generated.
'''),

    ('header_image',           False, str, '''
Like `welcome_image` for Windows, resized to 150 x 57 pixels.
'''),

    ('icon_image',             False, str, '''
Like `welcome_image` for Windows, resized to 256 x 256 pixels.
'''),
]


def ns_platform(platform):
    return dict(
        linux = platform.startswith('linux-'),
        linux32 = bool(platform == 'linux-32'),
        linux64 = bool(platform == 'linux-64'),
        armv7l = bool(platform == 'linux-armv7l'),
        ppc64le = bool(platform == 'linux-ppc64le'),
        osx = platform.startswith('osx-'),
        unix = platform.startswith(('linux-', 'osx-')),
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


def verify(info):
    types_key = {} # maps key to types
    required_keys = set()
    for key, required, types, unused_descr in KEYS:
        types_key[key] = types
        if required:
            required_keys.add(key)

    for key in info:
        if key not in types_key:
            sys.exit("Error: unknown key '%s' in construct.yaml" % key)
        if not isinstance(info[key], types_key[key]):
            sys.exit("Error: key '%s' points to wrong type" % key)

    for key in required_keys:
        if key not in info:
            sys.exit("Error: Required key '%s' not found in construct.yaml" %
                     key)
