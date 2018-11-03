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
from os.path import getsize, isdir, isfile, join
import sys

from constructor.utils import md5_file
from .conda_interface import (PackageCacheData, PackageCacheRecord, Solver, concatv, conda_context,
                              conda_reset_context, download, env_vars, groupby, read_paths_json)


def warn_menu_packages_missing(precs, menu_packages):
    all_names = set(prec.name for prec in precs)
    for name in menu_packages:
        if name not in all_names:
            print("WARNING: no such package (in menu_packages): %s" % name)


def check_duplicates(precs):
    groups = groupby(lambda x: x.name, precs)
    for precs in groups.values():
        if len(precs) > 1:
            sys.exit("Error: '%s' listed multiple times: %s" %
                     (precs[0].name, ', '.join(prec.fn for prec in precs)))


def exclude_packages(precs, exclude=()):
    for name in exclude:
        for bad_char in ' =<>*':
            if bad_char in name:
                sys.exit("Error: did not expect '%s' in package name: %s" % (bad_char, name))

    groups = groupby(lambda x: x.name in exclude, precs)
    excluded_precs = groups.get(True, [])
    accepted_precs = groups.get(False, [])
    for name in exclude:
        if not any(prec.name == name for prec in excluded_precs):
            sys.exit("Error: no package named '%s' to remove" % name)
    return accepted_precs


def _show(name, version, platform, download_dir, precs):
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
    print("number of package: %d" % len(precs))
    for prec in precs:
        print('    %s' % prec.fn)
    print()


def _fetch(download_dir, precs):
    assert conda_context.pkgs_dirs[0] == download_dir
    pc = PackageCacheData(download_dir)
    assert pc.is_writable

    for prec in precs:
        package_tarball_full_path = join(download_dir, prec.fn)
        extracted_package_dir = package_tarball_full_path[:-8]

        if not (isfile(package_tarball_full_path)
                and md5_file(package_tarball_full_path) == prec.md5):
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

    return tuple(pc.iter_records())


def check_duplicates_files(pc_recs, platform, ignore_duplicate_files=False):
    print('Checking for duplicate files ...')

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

    for member in map_members_scase:
        fns = map_members_scase[member]
        msg_str = "File '%s' found in multiple packages: %s" % (
                  member, ', '.join(fns))
        if len(fns) > 1:
            if ignore_duplicate_files:
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
            if ignore_duplicate_files or platform.startswith('linux'):
                print('Warning: {}'.format(msg_str))
            else:
                sys.exit('Error: {}'.format(msg_str))

    return total_tarball_size, total_extracted_pkgs_size


def _main(name, version, download_dir, platform, channel_urls=(), channels_remap=(), specs=(),
          exclude=(), menu_packages=(), install_in_dependency_order=True,
          ignore_duplicate_files=False, verbose=True, dry_run=False):

    # Add python to specs, since all installers need a python interpreter. In the future we'll
    # probably want to add conda too.
    specs = list(concatv(specs, ("python",)))
    if verbose:
        print("specs: %r" % specs)

    # Append channels_remap srcs to channel_urls
    channel_urls = tuple(concatv(
        channel_urls,
        (x['src'] for x in channels_remap),
    ))

    solver = Solver(
        # The Solver class doesn't do well with `None` as a prefix right now
        prefix="/constructor/no-environment",
        channels=channel_urls,
        subdirs=(platform, "noarch"),
        specs_to_add=specs,
    )
    precs = list(solver.solve_final_state())

    if not install_in_dependency_order:
        precs = sorted(precs, key="name")

    # move python first
    python_prec = next(prec for prec in precs if prec.name == "python")
    precs.remove(python_prec)
    precs.insert(0, python_prec)

    warn_menu_packages_missing(precs, menu_packages)
    check_duplicates(precs)
    precs = exclude_packages(precs, exclude)

    if verbose:
        _show(name, version, platform, download_dir, precs)

    if dry_run:
        return

    pc_recs = _fetch(download_dir, precs)
    # Constructor cache directory can have multiple packages from different
    # installer creations. Filter out those which the solver picked.
    precs_fns = [x.fn for x in precs]
    pc_recs = [x for x in pc_recs if x.fn in precs_fns]

    _urls = [(pc_rec.url, pc_rec.md5) for pc_rec in pc_recs]

    approx_tarballs_size, approx_pkgs_size = check_duplicates_files(
        pc_recs, platform, ignore_duplicate_files
    )

    dists = list(prec.fn for prec in precs)

    return _urls, dists, approx_tarballs_size, approx_pkgs_size


def main(info, verbose=True, dry_run=False):
    name = info["name"]
    version = info["version"]
    download_dir = info["_download_dir"]
    platform = info["_platform"]
    channel_urls = info.get("channels", ())
    channels_remap = info.get('channels_remap', ())
    specs = info["specs"]
    exclude = info.get("exclude", ())
    menu_packages = info.get("menu_packages", ())
    install_in_dependency_order = info.get("install_in_dependency_order", True)
    ignore_duplicate_files = info.get("ignore_duplicate_files", False)

    if not channel_urls:
        sys.exit("Error: 'channels' is required")

    with env_vars({
        "CONDA_PKGS_DIRS": download_dir,
    }, conda_reset_context):
        _urls, dists, approx_tarballs_size, approx_pkgs_size = _main(
            name, version, download_dir, platform, channel_urls, channels_remap, specs,
              exclude, menu_packages, install_in_dependency_order,
              ignore_duplicate_files, verbose, dry_run
        )

    info["_urls"] = _urls
    info["_dists"] = dists
    info["_approx_tarballs_size"] = approx_tarballs_size
    info["_approx_pkgs_size"] = approx_pkgs_size
