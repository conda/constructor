# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.
"""
fcp (fetch conda packages) module
"""
from __future__ import absolute_import, division, print_function

from collections import defaultdict
import json
import os
from os.path import isdir, isfile, join, splitext
from itertools import groupby

import sys
import tempfile

from constructor.utils import hash_files, filename_dist
from .conda_interface import (PackageCacheData, PackageCacheRecord, Solver, SubdirData,
                              VersionOrder, conda_context, conda_replace_context_default,
                              download, env_vars, read_paths_json, all_channel_urls,
                              cc_platform, PrefixGraph)


def getsize(filename):
    """Return the size of a file, reported by os.lstat as opposed to os.stat."""
    # Symlinks might be reported as "not found" if they are provided by a
    # package's dependencies
    # We use lstat to obtain the size of the symlink, as opposed to the
    # size of the file it points to
    # From the docstring of the os.lstat function
    #    > On platforms that do not support symbolic links, this is an
    #    > alias for stat().
    # https://github.com/conda/constructor/issues/311
    # https://docs.python.org/3/library/os.html
    return os.lstat(filename).st_size


def warn_menu_packages_missing(precs, menu_packages):
    all_names = set(prec.name for prec in precs)
    for name in menu_packages:
        if name not in all_names:
            print("WARNING: no such package (in menu_packages): %s" % name)


def check_duplicates(precs):
    prec_groups = {key: tuple(value) for key, value in groupby(precs, lambda prec: prec.name)}

    for name, precs in prec_groups.items():
        filenames = sorted(prec.fn for prec in precs)
        if len(filenames) > 1:
            sys.exit(f"Error: {name} listed multiple times: {' , '.join(filenames)}")


def exclude_packages(precs, exclude=(), error_on_absence=True):
    for name in exclude:
        for bad_char in ' =<>*':
            if bad_char in name:
                sys.exit("Error: did not expect '%s' in package name: %s" % (bad_char, name))

    if error_on_absence:
        unknown_precs = set(exclude).difference(prec.name for prec in precs)
        if unknown_precs:
            sys.exit(f"Error: no package(s) named {', '.join(unknown_precs)} to remove")

    return [prec for prec in precs if prec.name not in exclude]


def _find_out_of_date_precs(precs, channel_urls, platform):
    out_of_date_package_records = {}
    for prec in precs:
        all_versions = SubdirData.query_all(prec.name, channels=channel_urls, subdirs=[platform])
        if all_versions:
            most_recent = max(all_versions, key=lambda package_version: (
                VersionOrder(package_version.version), package_version.build_number))
            prec_version = VersionOrder(prec.version)
            latest_version = VersionOrder(most_recent.version)
            if prec_version < latest_version or (prec_version == latest_version
                                                 and prec.build_number < most_recent.build_number):
                out_of_date_package_records[prec.name] = most_recent
    return out_of_date_package_records


def _show(name, version, platform, download_dir, precs, more_recent_versions={}):
    print("""
name: %(name)s
version: %(version)s
cache download location: %(download_dir)s
platform: %(platform)s""" % dict(
        name=name,
        version=version,
        platform=platform,
        download_dir=download_dir,
    ))
    print("number of packages: %d" % len(precs))
    for prec in precs:
        more_recent_version = more_recent_versions.get(prec.name, None)
        if more_recent_version:
            print('    %s (latest: %s)' % (prec.fn, more_recent_version))
        else:
            print('    %s' % prec.fn)
    print()


def _fetch(download_dir, precs):
    assert conda_context.pkgs_dirs[0] == download_dir
    pc = PackageCacheData.first_writable()
    assert pc.pkgs_dir == download_dir
    assert pc.is_writable, f"{download_dir} does not exist or is not writable"

    for prec in precs:
        package_tarball_full_path = join(download_dir, prec.fn)
        if package_tarball_full_path.endswith(".tar.bz2"):
            extracted_package_dir = package_tarball_full_path[:-8]
        elif package_tarball_full_path.endswith(".conda"):
            extracted_package_dir = package_tarball_full_path[:-6]

        if not (isfile(package_tarball_full_path)
                and hash_files([package_tarball_full_path]) == prec.md5):
            print('fetching: %s' % prec.fn)
            download(prec.url, join(download_dir, prec.fn))

        if not isdir(extracted_package_dir):
            from conda.gateways.disk.create import extract_tarball
            extract_tarball(package_tarball_full_path, extracted_package_dir)

        repodata_record_path = join(extracted_package_dir, 'info', 'repodata_record.json')

        with open(repodata_record_path, "w") as fh:
            json.dump(prec.dump(), fh, indent=2, sort_keys=True, separators=(',', ': '))

        package_cache_record = PackageCacheRecord.from_objects(
            prec,
            package_tarball_full_path=package_tarball_full_path,
            extracted_package_dir=extracted_package_dir,
        )
        pc.insert(package_cache_record)

    return list(dict.fromkeys(PrefixGraph(pc.iter_records()).graph))


def check_duplicates_files(pc_recs, platform, duplicate_files="error"):
    assert duplicate_files in ("warn", "skip", "error")

    map_members_scase = defaultdict(set)
    map_members_icase = defaultdict(lambda: {'files': set(), 'fns': set()})

    # Keep a min, 50MB buffer size
    total_tarball_size = 52428800
    total_extracted_pkgs_size = 52428800

    for pc_rec in pc_recs:
        fn = pc_rec.fn
        extracted_package_dir = pc_rec.extracted_package_dir

        total_tarball_size += int(pc_rec.get("size", 0))

        paths_data = read_paths_json(extracted_package_dir).paths
        for path_data in paths_data:
            short_path = path_data.path
            try:
                size = (path_data.size_in_bytes or
                        getsize(join(extracted_package_dir, short_path)))
            except AttributeError:
                size = getsize(join(extracted_package_dir, short_path))
            total_extracted_pkgs_size += size

            map_members_scase[short_path].add(fn)

            short_path_lower = short_path.lower()
            map_members_icase[short_path_lower]['files'].add(short_path)
            map_members_icase[short_path_lower]['fns'].add(fn)

    if duplicate_files == "skip":
        return total_tarball_size, total_extracted_pkgs_size

    print('Checking for duplicate files ...')
    for member in map_members_scase:
        fns = map_members_scase[member]
        if len(fns) > 1:
            msg_str = "File '%s' found in multiple packages: %s" % (
                    member, ', '.join(fns))
            if duplicate_files == "warn":
                print('Warning: {}'.format(msg_str))
            else:
                sys.exit('Error: {}'.format(msg_str))

    for member in map_members_icase:
        # Some filesystems are not case sensitive by default (e.g HFS)
        # Throw warning on linux and error out on macOS/windows
        fns = map_members_icase[member]['fns']
        files = list(map_members_icase[member]['files'])
        msg_str = "Files %s found in the package(s): %s" % (
            str(files)[1:-1], ', '.join(fns))
        if len(files) > 1:
            msg_str = "Files %s found in the package(s): %s" % (
                str(files)[1:-1], ', '.join(fns))
            if duplicate_files == "warn" or platform.startswith('linux'):
                print('Warning: {}'.format(msg_str))
            else:
                sys.exit('Error: {}'.format(msg_str))

    return total_tarball_size, total_extracted_pkgs_size


def _precs_from_environment(environment, download_dir, user_conda):
    from subprocess import check_output

    # get basic data about the environment's packages
    list_flag = "--prefix" if isdir(environment) else "--name"
    json_listing = check_output([user_conda, "list", list_flag, environment, "--json"])
    listing = json.loads(json_listing)
    packages = {p["dist_name"]: p for p in listing}
    # get the package install order and MD5 sums,
    # creating a tuple of dist_name, URL, MD5, filename (fn)
    explicit = check_output([user_conda, "list", list_flag, environment,
                             "--explicit", "--json", "--md5"],
                            universal_newlines=True)
    ordering = []
    for line in explicit.splitlines():
        if not line or line.startswith("#") or line.startswith("@"):
            continue
        url, _, md5 = line.rpartition("#")
        _, _, fn = url.rpartition("/")
        if fn.endswith(".tar.bz2"):
            dist_name = fn[:-8]
        else:
            dist_name, _ = splitext(fn)
        ordering.append((dist_name, url, md5, fn))

    # now, create PackageCacheRecords
    precs = []
    for dist_name, url, md5, fn in ordering:
        package = packages[dist_name]
        package_tarball_full_path = join(download_dir, fn)
        extracted_package_dir = join(download_dir, dist_name)
        if 'platform' in package:
            package['subdir'] = package['platform']
            del package['platform']
        precs.append(PackageCacheRecord(url=url, md5=md5, fn=fn,
                                        package_tarball_full_path=package_tarball_full_path,
                                        extracted_package_dir=extracted_package_dir,
                                        **package))
    # topological sort + deduplication
    return list(dict.fromkeys(PrefixGraph(precs).graph))


def _solve_precs(name, version, download_dir, platform, channel_urls=(), channels_remap=(), specs=(),
                 exclude=(), menu_packages=(), environment=None, environment_file=None,
                 verbose=True, conda_exe="conda.exe", extra_env=False):
    # Add python to specs, since all installers need a python interpreter. In the future we'll
    # probably want to add conda too.
    # JRG: This only applies to the `base` environment; `extra_envs` are exempt
    if not extra_env:
        specs = (*specs, "python")
    if verbose:
        if environment:
            print(f"specs: <from existing environment '{environment}'>")
        elif environment_file:
            print(f"specs: <from environment file '{environment_file}'>")
        else:
            print("specs:", specs)

    # Append channels_remap srcs to channel_urls
    channel_urls = (*channel_urls, *(x['src'] for x in channels_remap))

    if environment_file or environment:
        # set conda to be the user's conda (what is in the environment)
        # for purpose of getting & building environments, rather
        # than the standalone conda (conda_exe). Fallback to the
        # standalone, if needed
        user_conda = os.environ.get('CONDA_EXE', '')
        if not user_conda:
            if cc_platform == platform:
                # We can use the standalone conda for native platforms if there is no
                # conda to be installed in the environment.
                user_conda = conda_exe
            else:
                # We need a conda for the native platform in order to do environment
                # based installations.
                sys.exit("CONDA_EXE env variable is empty. Need to activate a conda env.")
    # make the environment, if needed
    if environment_file:
        from subprocess import check_call
        environment = tempfile.mkdtemp()
        new_env = os.environ.copy()
        new_env["CONDA_SUBDIR"] = platform
        check_call([user_conda, "env", "create", "--file", environment_file,
                    "--prefix", environment, "--quiet"], universal_newlines=True, env=new_env)
    # obtain the package records
    if environment:
        precs = _precs_from_environment(environment, download_dir, user_conda)
    else:
        solver = Solver(
            # The Solver class doesn't do well with `None` as a prefix right now
            prefix="/constructor/no-environment",
            channels=channel_urls,
            subdirs=(platform, "noarch"),
            specs_to_add=specs,
        )
        # the records are already returned in topological sort
        precs = list(solver.solve_final_state())


    python_prec = next((prec for prec in precs if prec.name == "python"), None)
    if python_prec:
        precs.remove(python_prec)
        precs.insert(0, python_prec)
    elif not extra_env:
        # the base environment must always have python; this has been addressed
        # at the beginning of _main() but we can still get here through the
        # environment_file option
        sys.exit("python MUST be part of the base environment")

    warn_menu_packages_missing(precs, menu_packages)
    check_duplicates(precs)

    precs = exclude_packages(precs, exclude, error_on_absence=not extra_env)
    if verbose:
        more_recent_versions = _find_out_of_date_precs(precs, channel_urls, platform)
        _show(name, version, platform, download_dir, precs, more_recent_versions)

    if environment_file:
        import shutil

        shutil.rmtree(environment)

    return precs


def _fetch_precs(precs, download_dir, transmute_file_type=''):
    pc_recs = _fetch(download_dir, precs)
    # Constructor cache directory can have multiple packages from different
    # installer creations. Filter out those which the solver picked.
    precs_fns = [x.fn for x in precs]
    pc_recs = [x for x in pc_recs if x.fn in precs_fns]
    _urls = [(pc_rec.url, pc_rec.md5) for pc_rec in pc_recs]
    has_conda = any(pc_rec.name == 'conda' for pc_rec in pc_recs)

    dists = list(prec.fn for prec in precs)

    if transmute_file_type != '':
        new_dists = []
        import conda_package_handling.api
        for dist in dists:
            if dist.endswith(transmute_file_type):
                new_dists.append(dist)
            elif dist.endswith(".tar.bz2"):
                dist = filename_dist(dist)
                new_file_name = "%s%s" % (dist[:-8], transmute_file_type)
                new_dists.append(new_file_name)
                new_file_name = os.path.join(download_dir, new_file_name)
                if os.path.exists(new_file_name):
                    continue
                print("transmuting %s" % dist)
                conda_package_handling.api.transmute(os.path.join(download_dir, dist),
                    transmute_file_type, out_folder=download_dir)
            else:
                new_dists.append(dist)
        dists = new_dists

    return pc_recs, _urls, dists, has_conda


def _main(name, version, download_dir, platform, channel_urls=(), channels_remap=(), specs=(),
          exclude=(), menu_packages=(), ignore_duplicate_files=True, environment=None,
          environment_file=None, verbose=True, dry_run=False, conda_exe="conda.exe",
          transmute_file_type='', extra_envs=None):
    precs = _solve_precs(
        name, version, download_dir, platform, channel_urls=channel_urls,
        channels_remap=channels_remap, specs=specs, exclude=exclude,
        menu_packages=menu_packages, environment=environment,
        environment_file=environment_file, verbose=verbose, conda_exe=conda_exe
    )

    extra_envs_precs = {}
    for env_name, env_config in (extra_envs or {}).items():
        if not any(prec.name == "conda" for prec in precs):
            raise RuntimeError("conda needs to be present in `base` environment for extra_envs to work")

        if verbose:
            print("Solving extra environment:", env_name)
        extra_envs_precs[env_name] = _solve_precs(
            f"{name}/envs/{env_name}", version, download_dir, platform,
            channel_urls=env_config.get("channels", channel_urls),
            channels_remap=env_config.get("channels_remap", channels_remap),
            specs=env_config.get("specs", ()),
            exclude=env_config.get("exclude", exclude),
            menu_packages=env_config.get("menu_packages", ()),
            environment=env_config.get("environment"),
            environment_file=env_config.get("environment_file"),
            verbose=verbose,
            conda_exe=conda_exe,
            extra_env=True,
        )
    if dry_run:
        return None, None, None, None, None, None
    pc_recs, _urls, dists, has_conda = _fetch_precs(
        precs, download_dir, transmute_file_type=transmute_file_type
    )
    all_pc_recs = pc_recs.copy()

    extra_envs_data = {}
    for env_name, env_precs in extra_envs_precs.items():
        env_pc_recs, env_urls, env_dists, _ = _fetch_precs(
            env_precs, download_dir, transmute_file_type=transmute_file_type
        )
        extra_envs_data[env_name] = {"_urls": env_urls, "_dists": env_dists}
        all_pc_recs += env_pc_recs

    duplicate_files = "warn" if ignore_duplicate_files else "error"
    if extra_envs_data:  # this can cause false positives
        print("Info: Skipping duplicate files checks because `extra_envs` in use")
        duplicate_files = "skip"

    all_pc_recs = list({rec: None for rec in all_pc_recs}) # deduplicate
    approx_tarballs_size, approx_pkgs_size = check_duplicates_files(
        pc_recs, platform, duplicate_files=duplicate_files
    )

    return _urls, dists, approx_tarballs_size, approx_pkgs_size, has_conda, extra_envs_data


def main(info, verbose=True, dry_run=False, conda_exe="conda.exe"):
    name = info["name"]
    version = info["version"]
    download_dir = info["_download_dir"]
    platform = info["_platform"]
    channel_urls = all_channel_urls(info.get("channels", ()), subdirs=[platform, "noarch"])
    channels_remap = info.get('channels_remap', ())
    specs = info.get("specs", ())
    exclude = info.get("exclude", ())
    menu_packages = info.get("menu_packages", ())
    ignore_duplicate_files = info.get("ignore_duplicate_files", True)
    environment = info.get("environment", None)
    environment_file = info.get("environment_file", None)
    transmute_file_type = info.get("transmute_file_type", "")
    extra_envs = info.get("extra_envs", {})

    if not channel_urls and not channels_remap:
        sys.exit("Error: at least one entry in 'channels' or 'channels_remap' is required")

    # We need to preserve the configuration for proxy servers and ssl, otherwise if constructor is running
    # in a host that sits behind proxy (usually in a company / corporate environment) it will have this
    # settings reset with the call to conda_replace_context_default
    # See: https://github.com/conda/constructor/issues/304
    proxy_servers = conda_context.proxy_servers
    ssl_verify = conda_context.ssl_verify

    with env_vars({
        "CONDA_PKGS_DIRS": download_dir,
    }, conda_replace_context_default):
        # Restoring the state for both "proxy_servers" and "ssl_verify" to what was before
        conda_context.proxy_servers = proxy_servers
        conda_context.ssl_verify = ssl_verify

        (_urls, dists, approx_tarballs_size, approx_pkgs_size,
        has_conda, extra_envs_info) = _main(
            name, version, download_dir, platform, channel_urls, channels_remap, specs,
            exclude, menu_packages, ignore_duplicate_files, environment, environment_file,
            verbose, dry_run, conda_exe, transmute_file_type, extra_envs
        )

    info["_urls"] = _urls  # needed to mock the repodata cache
    info["_dists"] = dists  # needed to tell conda what to install
    info["_approx_tarballs_size"] = approx_tarballs_size
    info["_approx_pkgs_size"] = approx_pkgs_size
    info["_has_conda"] = has_conda
    # contains {env_name: [_dists, _urls]} for each extra environment
    info["_extra_envs_info"] = extra_envs_info
