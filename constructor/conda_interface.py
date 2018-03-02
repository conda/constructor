# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

import json
from os.path import join
import sys

try:
    from conda import __version__ as CONDA_INTERFACE_VERSION
    conda_interface_type = 'conda'
except ImportError:
    raise RuntimeError("Conda must be installed for python interpreter\n"
            "with sys.prefix: %s" % sys.prefix)

if conda_interface_type == 'conda':
    CONDA_MAJOR_MINOR = tuple(int(x) for x in CONDA_INTERFACE_VERSION.split('.')[:2])

    from conda.base.context import context
    cc_platform = context.subdir

    from conda.exports import fetch_index as _fetch_index, cache_fn_url as _cache_fn_url
    from conda.exports import Resolve, NoPackagesFound
    from conda.exports import default_prefix
    from conda.exports import linked_data
    from conda.exports import download as _download

    from conda.models.channel import prioritize_channels

    def fetch_index(channel_urls):
        return _fetch_index(prioritize_channels(channel_urls))

    def fetch_pkg(pkginfo, download_dir):
        pkg_url = pkginfo['url']
        assert pkg_url
        _download(pkg_url, join(download_dir, pkginfo['fn']))

    def write_repodata(cache_dir, url):
        if CONDA_MAJOR_MINOR >= (4, 5):
            from conda.core.subdir_data import fetch_repodata_remote_request
            raw_repodata_str = fetch_repodata_remote_request(url, None, None)
            repodata_filename = _cache_fn_url(url)
            with open(join(cache_dir, repodata_filename), 'w') as fh:
                fh.write(raw_repodata_str)
        elif CONDA_MAJOR_MINOR >= (4, 4):
            from conda.core.repodata import fetch_repodata_remote_request
            raw_repodata_str = fetch_repodata_remote_request(url, None, None)
            repodata_filename = _cache_fn_url(url)
            with open(join(cache_dir, repodata_filename), 'w') as fh:
                fh.write(raw_repodata_str)
        elif CONDA_MAJOR_MINOR >= (4, 3):
            from conda.core.repodata import fetch_repodata_remote_request
            repodata_obj = fetch_repodata_remote_request(None, url, None, None)
            raw_repodata_str = json.dumps(repodata_obj)
            repodata_filename = _cache_fn_url(url)
            with open(join(cache_dir, repodata_filename), 'w') as fh:
                fh.write(raw_repodata_str)
        else:
            raise NotImplementedError("unsupported version of conda: %s" % CONDA_INTERFACE_VERSION)


cc_platform = cc_platform
fetch_index, fetch_pkg = fetch_index, fetch_pkg
Resolve, NoPackagesFound = Resolve, NoPackagesFound
default_prefix = default_prefix
linked_data = linked_data
