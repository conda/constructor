# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

import json
import os
import sys
from copy import deepcopy
from itertools import chain
from os.path import join
import datetime

from constructor.utils import hash_files

NAV_APPS = ['glueviz', 'jupyterlab', 'notebook',
            'orange3', 'qtconsole', 'rstudio', 'spyder', 'vscode']

try:
    from conda import __version__ as CONDA_INTERFACE_VERSION
    conda_interface_type = 'conda'
except ImportError:
    raise RuntimeError("Conda must be installed for python interpreter\n"
                       "with sys.prefix: %s" % sys.prefix)

if conda_interface_type == 'conda':
    # This import path has been stable since 2016
    from conda.models.version import VersionOrder

    _conda_version = VersionOrder(CONDA_INTERFACE_VERSION).version
    # Flatten VersionOrder.version, skip epoch, and keep only major and minor
    CONDA_MAJOR_MINOR = tuple(chain.from_iterable(_conda_version))[1:3]

    from conda.api import SubdirData # noqa
    from conda.base.context import (
        context as _conda_context, replace_context_default as _conda_replace_context_default,
    )
    from conda.common.io import env_vars as _env_vars
    from conda.core.package_cache_data import (
        PackageCacheData as _PackageCacheData,
    )
    from conda.core.prefix_data import PrefixData as _PrefixData
    from conda.exports import default_prefix as _default_prefix
    from conda.models.channel import all_channel_urls as _all_channel_urls
    from conda.gateways.disk.read import read_paths_json as _read_paths_json
    from conda.models.dist import Dist as _Dist
    from conda.exports import MatchSpec as _MatchSpec
    from conda.exports import download as _download
    from conda.models.version import VersionOrder # noqa
    from conda.models.prefix_graph import PrefixGraph as _PrefixGraph
    try:
        from conda.models.records import PackageCacheRecord as _PackageCacheRecord
    except ImportError:
        from conda.models.package_cache_record import PackageCacheRecord as _PackageCacheRecord
    try:
        from conda.core.solve import _get_solver_class
        _Solver = _get_solver_class()
    except ImportError:
        from conda.core.solve import Solver as _Solver

    # used by fcp.py
    PackageCacheData = _PackageCacheData
    PrefixGraph = _PrefixGraph
    Solver, read_paths_json = _Solver, _read_paths_json
    all_channel_urls = _all_channel_urls
    conda_context, env_vars = _conda_context, _env_vars
    conda_replace_context_default = _conda_replace_context_default
    download, PackageCacheRecord = _download, _PackageCacheRecord

    # used by preconda.py
    Dist, MatchSpec, PrefixData, default_prefix = _Dist, _MatchSpec, _PrefixData, _default_prefix

    cc_platform = conda_context.subdir

    from conda.exports import cache_fn_url as _cache_fn_url

    distro = None
    if sys.platform.startswith('linux'):
        try:
            from conda._vendor import distro
        except ImportError:
            pass

    def get_repodata(url):
        if CONDA_MAJOR_MINOR >= (4, 5):
            from conda.core.subdir_data import fetch_repodata_remote_request
            raw_repodata_str = fetch_repodata_remote_request(url, None, None)
        elif CONDA_MAJOR_MINOR >= (4, 4):
            from conda.core.repodata import fetch_repodata_remote_request
            raw_repodata_str = fetch_repodata_remote_request(url, None, None)
        elif CONDA_MAJOR_MINOR >= (4, 3):
            from conda.core.repodata import fetch_repodata_remote_request
            repodata_obj = fetch_repodata_remote_request(None, url, None, None)
            raw_repodata_str = json.dumps(repodata_obj)
        else:
            raise NotImplementedError("unsupported version of conda: %s" % CONDA_INTERFACE_VERSION)

        # noarch-only repos are valid. In this case, the architecture specific channel will return None
        if raw_repodata_str is None:
            full_repodata = {
                '_url': url,
                'info': {
                    'subdir': cc_platform
                },
                'packages': {},
                'packages.conda': {},
                'removed': []
            }
        else:
            full_repodata = json.loads(raw_repodata_str)

        return full_repodata

    def write_repodata(cache_dir, url, full_repodata, used_packages, info):
        used_repodata = {k: full_repodata[k] for k in
                         set(full_repodata.keys()) - {'packages', 'packages.conda', 'removed'}}
        used_repodata['packages.conda'] = {}
        used_repodata['removed'] = []
        used_repodata['packages'] = {
            k: v for k, v in full_repodata['packages'].items() if v['name'] in NAV_APPS}

        # Minify the included repodata
        for package in used_packages:
            key = 'packages.conda' if package.endswith(".conda") else 'packages'
            if package in full_repodata.get(key, {}):
                used_repodata[key][package] = full_repodata[key][package]
                continue
            # If we're transcoding packages, fix-up the metadata
            if package.endswith(".conda"):
                original_package = package[:-len(".conda")] + ".tar.bz2"
                original_key = "packages"
            elif package.endswith(".tar.bz2"):
                original_package = package[:-len(".tar.bz2")] + ".conda"
                original_key = "packages.conda"
            else:
                raise NotImplementedError("Package type is unknown for: %s" % package)
            if original_package in full_repodata.get(original_key, {}):
                data = deepcopy(full_repodata[original_key][original_package])
                pkg_fn = join(info["_download_dir"], package)
                data["size"] = os.stat(pkg_fn).st_size
                data["sha256"] = hash_files([pkg_fn], algorithm='sha256')
                data["md5"] = hash_files([pkg_fn])
                used_repodata[key][package] = data

        # The first line of the JSON should contain cache metadata
        # Choose an arbitrary old, expired date, so that conda will want to
        # immediately update it when not being run in offline mode
        url = used_repodata.pop('_url').rstrip("/")
        used_repodata.pop("_mod", None)
        repodata = json.dumps(used_repodata, indent=2)
        mod_time = "Mon, 07 Jan 2019 15:22:15 GMT"
        repodata_header = json.dumps(
            {
                "_mod": mod_time,
                "_url": url,
            }
        )
        repodata = repodata_header[:-1] + "," + repodata[1:]
        repodata_filepath = join(cache_dir, _cache_fn_url(url))
        with open(repodata_filepath, 'w') as fh:
            fh.write(repodata)

        # set the modification time to mod_time. needed for mamba
        mod_time_datetime = datetime.datetime.strptime(mod_time,
            "%a, %d %b %Y %H:%M:%S %Z")
        mod_time_s = int(mod_time_datetime.timestamp())
        os.utime(repodata_filepath, times=(mod_time_s, mod_time_s))

    def write_cache_dir():
        cache_dir = join(PackageCacheData.first_writable().pkgs_dir, 'cache')
        mkdir_p_sudo_safe(cache_dir)
        return cache_dir
