# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import os
from os.path import basename, dirname, isdir, join, split as path_split
import platform
import sys
import time

from .utils import filename_dist

from . import __version__ as CONSTRUCTOR_VERSION
from .conda_interface import (
    CONDA_INTERFACE_VERSION, Dist, MatchSpec, default_prefix, PrefixData, write_repodata,
)

try:
    import json
except:
    import ruamel_json as json

files = '.constructor-build.info'


def system_info():
    out = {'constructor': CONSTRUCTOR_VERSION,
           'conda': CONDA_INTERFACE_VERSION,
           'platform': sys.platform,
           'python': sys.version,
           'python_version': tuple(sys.version_info),
           'machine': platform.machine(),
           'platform_full': platform.version()}
    if sys.platform == 'darwin':
        out['extra'] = platform.mac_ver()
    elif sys.platform.startswith('linux'):
        out['extra'] = platform.dist()
    elif sys.platform.startswith('win'):
        out['extra'] = platform.win32_ver()
        prefix = default_prefix
        prefix_records = list(PrefixData(prefix).iter_records())
        nsis_prefix_rec = next(
            (rec for rec in prefix_records if rec.name == 'nsis'), None)
        if nsis_prefix_rec:
            out['nsis'] = nsis_prefix_rec.version
    return out


def write_files(info, dst_dir):
    with open(os.open(join(dst_dir, '.constructor-build.info'), os.O_CREAT | os.O_WRONLY, mode=0o664), 'w') as fo:
        json.dump(system_info(), fo)
