# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals
import sys

from os.path import join

try:
    from conda import __version__ as CONDA_INTERFACE_VERSION
    conda_interface_type = 'conda'
except ImportError:
    try:
        from libconda import __version__ as CONDA_INTERFACE_VERSION
        conda_interface_type = 'libconda'
    except ImportError:
        raise RuntimeError("Either conda or libconda must be installed for python interpreter\n"
                           "with sys.prefix: %s" % sys.prefix)

if conda_interface_type == 'conda':
    from conda.base.context import context
    cc_platform = context.subdir

    from conda.exports import fetch_index as _fetch_index
    from conda.exports import Resolve, NoPackagesFound

    from conda.exports import download

    from conda.models.channel import prioritize_channels

    def fetch_index(channel_urls):
        return _fetch_index(prioritize_channels(channel_urls))

    def fetch_pkg(pkginfo, download_dir):
        pkg_url = "%s/%s/%s" % (pkginfo['channel'].rstrip('/'), pkginfo['subdir'], pkginfo['fn'])
        download(pkg_url, join(download_dir, pkginfo['fn']))

else:
    from libconda.config import subdir as cc_platform
    from libconda.fetch import fetch_index, fetch_pkg
    from libconda.resolve import Resolve, NoPackagesFound


cc_platform = cc_platform
fetch_index, fetch_pkg = fetch_index, fetch_pkg
Resolve, NoPackagesFound = Resolve, NoPackagesFound
