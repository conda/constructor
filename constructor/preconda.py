# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.
"""
Common logic to prepare the tarball payloads shipped in some installers.
"""

from __future__ import annotations

import platform
import shutil
import sys
import time
from pathlib import Path
from textwrap import dedent

from . import __version__ as CONSTRUCTOR_VERSION
from .conda_interface import (
    CONDA_INTERFACE_VERSION,
    Dist,
    MatchSpec,
    PrefixData,
    all_channel_urls,
    default_prefix,
    get_repodata,
    write_repodata,
)
from .conda_interface import distro as conda_distro
from .utils import (
    ensure_transmuted_ext,
    filename_dist,
    get_final_channels,
    get_final_url,
    shortcuts_flags,
)

try:
    import json
except ImportError:
    import ruamel_json as json

files = (
    "pkgs/.constructor-build.info",
    "pkgs/urls",
    "pkgs/urls.txt",
    "conda-meta/initial-state.explicit.txt",
)


def write_index_cache(info, dst_dir: Path, used_packages):
    cache_dir = dst_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    _platforms = info["_platform"], "noarch"
    _remap_configs = list(info.get("channels_remap", []))
    _env_channels = []
    for env_info in info.get("extra_envs", {}).values():
        _remap_configs += env_info.get("channels_remap", [])
        _env_channels += env_info.get("channels", [])

    _remaps = {url["src"].rstrip("/"): url["dest"].rstrip("/") for url in _remap_configs}
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
        src, subdir, fn = url.rsplit("/", 2)
        dst = _remaps.get(src)
        if dst is not None:
            src = "%s/%s" % (src, subdir)
            dst = "%s/%s" % (dst, subdir)
            if dst not in repodatas:
                repodatas[dst] = {
                    "_url": dst,
                    "info": {"subdir": subdir},
                    "packages": {},
                    "packages.conda": {},
                    "removed": [],
                }
            loc = "packages.conda" if fn.endswith(".conda") else "packages"
            repodatas[dst][loc][fn] = repodatas[src][loc][fn]
    for src in _remaps:
        for subdir in _platforms:
            del repodatas["%s/%s" % (src, subdir)]

    for url, repodata in repodatas.items():
        if repodata is not None:
            write_repodata(cache_dir, url, repodata, used_packages, info)

    for cache_file in cache_dir.glob("*"):
        if not cache_file.suffix == ".json":
            cache_file.unlink()


def system_info():
    out = {
        "constructor": CONSTRUCTOR_VERSION,
        "conda": CONDA_INTERFACE_VERSION,
        "platform": sys.platform,
        "python": sys.version,
        "python_version": tuple(sys.version_info),
        "machine": platform.machine(),
        "platform_full": platform.version(),
    }
    if sys.platform == "darwin":
        out["extra"] = platform.mac_ver()
    elif sys.platform.startswith("linux"):
        if conda_distro is not None:
            out["extra"] = conda_distro.linux_distribution(full_distribution_name=False)
        elif hasattr(platform, "dist"):
            out["extra"] = platform.dist()
    elif sys.platform.startswith("win"):
        out["extra"] = platform.win32_ver()
        prefix = default_prefix
        prefix_records = list(PrefixData(prefix).iter_records())
        nsis_prefix_rec = next((rec for rec in prefix_records if rec.name == "nsis"), None)
        if nsis_prefix_rec:
            out["nsis"] = nsis_prefix_rec.version
    return out


def write_files(info: dict, workspace: Path):
    """
    Prepare files on disk to be shipped as part of the pre-conda payload, mostly
    configuration and metadata files:

    - `conda-meta/initial-state.explicit.txt`: Lockfile to provision the base environment.
    - `conda-meta/history`: Prepared history file with the right requested specs in input file.
    - `pkgs/urls` and `pkgs/urls.txt`: Direct URLs of packages used, with and without MD5 hashes.
    - `pkgs/cache/*.json`: Trimmed repodata to mock offline channels in use.
    - `pkgs/channels.txt`: Channels in use.
    - `pkgs/shortcuts.txt`: Which packages should have their shortcuts created, if any.

    If extra envs are requested, this will also write:

    - Their corresponding `envs/<env-name>/conda-meta/` files.
    - Their corresponding `pkgs/channels.txt` and `pkgs/shortcuts.txt` under
      `pkgs/envs/<env-name>`.
    """
    (workspace / "conda-meta").mkdir(exist_ok=True)
    pkgs_dir = workspace / "pkgs"
    pkgs_dir.mkdir(exist_ok=True)
    (pkgs_dir / ".constructor-build.info").write_text(json.dumps(system_info()))

    all_urls = info["_urls"].copy()
    for env_info in info.get("_extra_envs_info", {}).values():
        all_urls += env_info["_urls"]

    final_urls_md5s = tuple((get_final_url(info, url), md5) for url, md5 in info["_urls"])
    all_final_urls_md5s = tuple((get_final_url(info, url), md5) for url, md5 in all_urls)

    with open(pkgs_dir / "urls", "w") as fo:
        for url, md5 in all_final_urls_md5s:
            maybe_different_url = ensure_transmuted_ext(info, url)
            if maybe_different_url != url:  # transmuted, no md5
                fo.write(f"{maybe_different_url}\n")
            else:
                fo.write(f"{url}#{md5}\n")

    (pkgs_dir / "urls.txt").write_text("".join([f"{url}\n" for url, _ in all_final_urls_md5s]))

    all_dists = info["_dists"].copy()
    for env_info in info.get("_extra_envs_info", {}).values():
        all_dists += env_info["_dists"]
    all_dists = list({dist: None for dist in all_dists})  # de-duplicate

    write_index_cache(info, pkgs_dir, all_dists)

    # base environment conda-meta
    write_conda_meta(info, workspace / "conda-meta", final_urls_md5s)

    write_repodata_record(info, pkgs_dir)

    # base environment file used with conda install --file
    # (list of specs/dists to install)
    write_initial_state_explicit_txt(info, workspace / "conda-meta", final_urls_md5s)

    for fn in files:
        (workspace / fn).chmod(0o664)

    for env_name, env_info in info.get("_extra_envs_info", {}).items():
        env_config = info["extra_envs"][env_name]
        env_pkgs = workspace / "pkgs" / "envs" / env_name
        env_conda_meta = workspace / "envs" / env_name / "conda-meta"
        env_pkgs.mkdir(parents=True, exist_ok=True)
        env_conda_meta.mkdir(parents=True, exist_ok=True)
        # environment conda-meta
        env_urls_md5 = tuple((get_final_url(info, url), md5) for url, md5 in env_info["_urls"])
        user_requested_specs = env_config.get("user_requested_specs", env_config.get("specs", ()))
        write_conda_meta(info, env_conda_meta, env_urls_md5, user_requested_specs)
        # environment installation list
        write_initial_state_explicit_txt(info, env_conda_meta, env_urls_md5)
        # channels
        write_channels_txt(info, env_pkgs, env_config)
        # shortcuts
        write_shortcuts_txt(info, env_pkgs, env_config)


def write_conda_meta(info, dst_dir: Path, final_urls_md5s, user_requested_specs=None):
    if user_requested_specs is None:
        user_requested_specs = info.get("user_requested_specs", info.get("specs", ()))

    cmd = Path(sys.argv[0]).name
    if len(sys.argv) > 1:
        cmd = "%s %s" % (cmd, " ".join(sys.argv[1:]))

    builder = [
        "==> %s <==" % time.strftime("%Y-%m-%d %H:%M:%S"),
        "# cmd: %s" % cmd,
    ]
    dists = tuple(Dist(url) for url, _ in final_urls_md5s)

    builder.extend("+%s" % dist.full_name for dist in dists)
    if user_requested_specs:
        update_specs = [str(MatchSpec(s)) for s in user_requested_specs]
        builder.append("# update specs: %s" % update_specs)
    builder.append("\n")

    (dst_dir / "history").write_text("\n".join(builder))


def write_repodata_record(info, dst_dir: Path):
    all_dists = info["_dists"].copy()
    for env_data in info.get("_extra_envs_info", {}).values():
        all_dists += env_data["_dists"]
    for dist in all_dists:
        if filename_dist(dist).endswith(".conda"):
            _dist = filename_dist(dist)[:-6]
        elif filename_dist(dist).endswith(".tar.bz2"):
            _dist = filename_dist(dist)[:-8]
        record_file = Path(_dist, "info", "repodata_record.json")
        record_file_src = info["_download_dir"] / record_file
        record_file_dst = dst_dir / record_file
        rr_json = json.loads(record_file_src.read_text())
        rr_json["url"] = get_final_url(info, rr_json["url"])
        rr_json["channel"] = get_final_url(info, rr_json["channel"])

        record_file_dst.parent.mkdir(parents=True, exist_ok=True)
        record_file_dst.write_text(json.dumps(rr_json, indent=2, sort_keys=True))


def write_initial_state_explicit_txt(info, dst_dir, urls):
    """
    urls is an iterable of tuples with url and md5 values
    """
    header = dedent(
        f"""
        # This file may be used to create an environment using:
        # $ conda create --name <env> --file <this file>
        # platform: {info["_platform"]}
        @EXPLICIT
        """
    ).lstrip()
    with open(dst_dir / "initial-state.explicit.txt", "w") as envf:
        envf.write(header)
        for url, md5 in urls:
            maybe_different_url = ensure_transmuted_ext(info, url)
            if maybe_different_url != url:  # transmuted, no md5
                envf.write(f"{maybe_different_url}\n")
            else:
                envf.write(f"{url}#{md5}\n")


def write_channels_txt(info, dst_dir: Path, env_config):
    env_config = env_config.copy()
    if "channels" not in env_config:
        env_config["channels"] = info.get("channels", ())
    if "channels_remap" not in env_config:
        env_config["channels_remap"] = info.get("channels_remap", ())

    (dst_dir / "channels.txt").write_text(",".join(get_final_channels(env_config)))


def write_shortcuts_txt(info, dst_dir, env_config):
    if "menu_packages" in env_config:
        contents = shortcuts_flags(env_config)
    else:
        contents = shortcuts_flags(info)
    (dst_dir / "shortcuts.txt").write_text(contents)


def copy_extra_files(
    extra_files: list[str | Path | dict[str | Path, str]], workdir: Path
) -> list[Path]:
    """Copy list of extra files to a working directory

    Args:
        extra_files: A path or a mapping
        workdir: Path to where extra files will be copied to.

    Raises:
        FileNotFoundError: Raises when the file isn't found.

    Returns:
        list[Path]: List of normalized paths of copied locations.
    """
    if not extra_files:
        return []
    copied = []
    workdir = Path(workdir)
    for path in extra_files:
        if isinstance(path, (str, Path)):
            copied.append(Path(shutil.copy(path, workdir)))
        elif isinstance(path, dict):
            assert len(path) == 1
            origin, destination = next(iter(path.items()))
            orig_path = Path(origin)
            if not orig_path.exists():
                raise FileNotFoundError(f"File {origin} does not exist.")
            dest_path = Path(workdir) / destination
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            copied.append(Path(shutil.copy(orig_path, dest_path)))
    return copied
