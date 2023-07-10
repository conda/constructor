# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import os
import platform
import shutil
import sys
import time
from os.path import isdir, join
from os.path import split as path_split
from pathlib import Path
from textwrap import dedent
from typing import List, Mapping, Union

from . import __version__ as CONSTRUCTOR_VERSION
from .conda_interface import (
    CONDA_INTERFACE_VERSION,
    Dist,
    MatchSpec,
    PrefixData,
    all_channel_urls,
    default_prefix,
)
from .conda_interface import distro as conda_distro
from .conda_interface import get_repodata, write_repodata
from .utils import ensure_transmuted_ext, filename_dist, get_final_channels, get_final_url

try:
    import json
except ImportError:
    import ruamel_json as json

files = '.constructor-build.info', 'urls', 'urls.txt', 'env.txt'


def write_index_cache(info, dst_dir, used_packages):
    cache_dir = join(dst_dir, 'cache')

    if not isdir(cache_dir):
        os.makedirs(cache_dir)

    _platforms = info['_platform'], 'noarch'
    _remap_configs = list(info.get("channels_remap", []))
    _env_channels = []
    for env_info in info.get("extra_envs", {}).values():
        _remap_configs += env_info.get("channels_remap", [])
        _env_channels += env_info.get("channels", [])

    _remaps = {url['src'].rstrip('/'): url['dest'].rstrip('/')
               for url in _remap_configs}
    _channels = [
        url.rstrip("/")
        for url in list(_remaps)
        + info.get("channels", [])
        + info.get("conda_default_channels", [])
        + _env_channels
    ]
    _urls = all_channel_urls(_channels, subdirs=_platforms)
    repodatas = {url: get_repodata(url) for url in _urls if url is not None}

    all_urls = info["_urls"].copy()
    for env_info in info.get("_extra_envs_info", {}).values():
        all_urls += env_info["_urls"]

    for url, _ in all_urls:
        src, subdir, fn = url.rsplit('/', 2)
        dst = _remaps.get(src)
        if dst is not None:
            src = '%s/%s' % (src, subdir)
            dst = '%s/%s' % (dst, subdir)
            if dst not in repodatas:
                repodatas[dst] = {
                    '_url': dst,
                    'info': {'subdir': subdir},
                    'packages': {},
                    'packages.conda': {},
                    'removed': []
                }
            loc = 'packages.conda' if fn.endswith('.conda') else 'packages'
            repodatas[dst][loc][fn] = repodatas[src][loc][fn]
    for src in _remaps:
        for subdir in _platforms:
            del repodatas['%s/%s' % (src, subdir)]

    for url, repodata in repodatas.items():
        if repodata is not None:
            write_repodata(cache_dir, url, repodata, used_packages, info)

    for cache_file in os.listdir(cache_dir):
        if not cache_file.endswith(".json"):
            os.unlink(join(cache_dir, cache_file))


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
        if conda_distro is not None:
            out['extra'] = conda_distro.linux_distribution(full_distribution_name=False)
        elif hasattr(platform, 'dist'):
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
    with open(join(dst_dir, '.constructor-build.info'), 'w') as fo:
        json.dump(system_info(), fo)

    all_urls = info["_urls"].copy()
    for env_info in info.get("_extra_envs_info", {}).values():
        all_urls += env_info["_urls"]

    final_urls_md5s = tuple((get_final_url(info, url), md5) for url, md5 in info["_urls"])
    all_final_urls_md5s = tuple((get_final_url(info, url), md5) for url, md5 in all_urls)

    with open(join(dst_dir, 'urls'), 'w') as fo:
        for url, md5 in all_final_urls_md5s:
            maybe_different_url = ensure_transmuted_ext(info, url)
            if maybe_different_url != url:  # transmuted, no md5
                fo.write(f"{maybe_different_url}\n")
            else:
                fo.write(f"{url}#{md5}\n")

    with open(join(dst_dir, 'urls.txt'), 'w') as fo:
        for url, _ in all_final_urls_md5s:
            fo.write('%s\n' % url)

    all_dists = info["_dists"].copy()
    for env_info in info.get("_extra_envs_info", {}).values():
        all_dists += env_info["_dists"]
    all_dists = list({dist: None for dist in all_dists})  # de-duplicate

    write_index_cache(info, dst_dir, all_dists)

    # base environment conda-meta
    write_conda_meta(info, dst_dir, final_urls_md5s)

    write_repodata_record(info, dst_dir)

    # base environment file used with conda install --file
    # (list of specs/dists to install)
    write_env_txt(info, dst_dir, final_urls_md5s)

    for fn in files:
        os.chmod(join(dst_dir, fn), 0o664)

    for env_name, env_info in info.get("_extra_envs_info", {}).items():
        env_config = info["extra_envs"][env_name]
        env_dst_dir = os.path.join(dst_dir, "envs", env_name)
        # environment conda-meta
        env_urls_md5 = tuple((get_final_url(info, url), md5) for url, md5 in env_info["_urls"])
        user_requested_specs = env_config.get('user_requested_specs', env_config.get('specs', ()))
        write_conda_meta(info, env_dst_dir, env_urls_md5, user_requested_specs)
        # environment installation list
        write_env_txt(info, env_dst_dir, env_urls_md5)
        # channels
        write_channels_txt(info, env_dst_dir, env_config)


def write_conda_meta(info, dst_dir, final_urls_md5s, user_requested_specs=None):
    if user_requested_specs is None:
        user_requested_specs = info.get('user_requested_specs', info.get('specs', ()))

    cmd = path_split(sys.argv[0])[-1]
    if len(sys.argv) > 1:
        cmd = "%s %s" % (cmd, " ".join(sys.argv[1:]))

    builder = [
        "==> %s <==" % time.strftime('%Y-%m-%d %H:%M:%S'),
        "# cmd: %s" % cmd,
    ]
    dists = tuple(Dist(url) for url, _ in final_urls_md5s)

    builder.extend("+%s" % dist.full_name for dist in dists)
    if user_requested_specs:
        update_specs = [str(MatchSpec(s)) for s in user_requested_specs]
        builder.append("# update specs: %s" % update_specs)
    builder.append("\n")

    if not isdir(join(dst_dir, 'conda-meta')):
        os.makedirs(join(dst_dir, 'conda-meta'))
    with open(join(dst_dir, 'conda-meta', 'history'), 'w') as fh:
        fh.write("\n".join(builder))


def write_repodata_record(info, dst_dir):
    all_dists = info["_dists"].copy()
    for env_data in info.get("_extra_envs_info", {}).values():
        all_dists += env_data["_dists"]
    for dist in all_dists:
        if filename_dist(dist).endswith(".conda"):
            _dist = filename_dist(dist)[:-6]
        elif filename_dist(dist).endswith(".tar.bz2"):
            _dist = filename_dist(dist)[:-8]
        record_file = join(_dist, 'info', 'repodata_record.json')
        record_file_src = join(info['_download_dir'], record_file)

        with open(record_file_src) as rf:
            rr_json = json.load(rf)

        rr_json['url'] = get_final_url(info, rr_json['url'])
        rr_json['channel'] = get_final_url(info, rr_json['channel'])

        if not isdir(join(dst_dir, _dist, 'info')):
            os.makedirs(join(dst_dir, _dist, 'info'))

        record_file_dest = join(dst_dir, record_file)

        with open(record_file_dest, 'w') as rf:
            json.dump(rr_json, rf, indent=2, sort_keys=True)


def write_env_txt(info, dst_dir, urls):
    """
    urls is an iterable of tuples with url and md5 values
    """
    header = dedent(
        f"""
        # This file may be used to create an environment using:
        # $ conda create --name <env> --file <this file>
        # platform: {info['_platform']}
        @EXPLICIT
        """
    ).lstrip()
    with open(join(dst_dir, "env.txt"), "w") as envf:
        envf.write(header)
        for url, md5 in urls:
            maybe_different_url = ensure_transmuted_ext(info, url)
            if maybe_different_url != url:  # transmuted, no md5
                envf.write(f"{maybe_different_url}\n")
            else:
                envf.write(f"{url}#{md5}\n")


def write_channels_txt(info, dst_dir, env_config):
    env_config = env_config.copy()
    if "channels" not in env_config:
        env_config["channels"] = info.get("channels", ())
    if "channels_remap" not in env_config:
        env_config["channels_remap"] = info.get("channels_remap", ())

    with open(join(dst_dir, "channels.txt"), "w") as f:
        f.write(",".join(get_final_channels(env_config)))


def copy_extra_files(
    extra_files: List[Union[os.PathLike, Mapping]], workdir: os.PathLike
) -> List[os.PathLike]:
    """Copy list of extra files to a working directory

    Args:
        extra_files (List[Union[os.PathLike, Mapping]]): A path or a mapping
        workdir (os.PathLike): Path to where extra files will be copied to.

    Raises:
        FileNotFoundError: Raises when the file isn't found.

    Returns:
        List[os.PathLike]: List of normalized paths of copied locations.
    """
    if not extra_files:
        return []
    copied = []
    for path in extra_files:
        if isinstance(path, str):
            copied.append(shutil.copy(path, workdir))
        elif isinstance(path, dict):
            assert len(path) == 1
            origin, destination = next(iter(path.items()))
            orig_path = Path(origin)
            if not orig_path.exists():
                raise FileNotFoundError(f"File {origin} does not exist.")
            dest_path = Path(workdir) / destination
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            copied.append(shutil.copy(orig_path, dest_path))
    return copied
