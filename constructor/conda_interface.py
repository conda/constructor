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

    from conda._vendor.toolz.itertoolz import (
        concatv as _concatv, get as _get, groupby as _groupby,
    )
    from conda.base.context import (
        context as _conda_context, reset_context as _conda_reset_context,
    )
    from conda.common.io import env_vars as _env_vars
    from conda.core.package_cache_data import (
        PackageCacheData as _PackageCacheData,
    )
    from conda.core.prefix_data import PrefixData as _PrefixData
    from conda.core.solve import Solver as _Solver
    from conda.exports import default_prefix as _default_prefix
    from conda.gateways.disk.read import read_paths_json as _read_paths_json
    from conda.models.dist import Dist as _Dist
    from conda.exports import MatchSpec as _MatchSpec
    from conda.exports import download as _download
    try:
        from conda.models.records import PackageCacheRecord as _PackageCacheRecord
    except ImportError:
        from conda.models.package_cache_record import PackageCacheRecord as _PackageCacheRecord

    # used by fcp.py
    PackageCacheData = _PackageCacheData
    Solver, read_paths_json = _Solver, _read_paths_json
    concatv, get, groupby = _concatv, _get, _groupby
    conda_context, env_vars, conda_reset_context = _conda_context, _env_vars, _conda_reset_context
    download, PackageCacheRecord = _download, _PackageCacheRecord

    # used by preconda.py
    Dist, MatchSpec, PrefixData, default_prefix = _Dist, _MatchSpec, _PrefixData, _default_prefix

    cc_platform = conda_context.subdir


    from conda.exports import cache_fn_url as _cache_fn_url

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

