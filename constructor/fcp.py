# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.
"""
fcp (fetch conda packages) module
"""
from __future__ import absolute_import, division, print_function

from glob import glob
import json
import os
import sys
import shutil

from .conda_interface import concatv, conda_reset_context, env_vars
from conda.cli import python_api
import cpr.api as prefix_api

from constructor.install import INSTALL_TMP_FOLDER


def warn_menu_packages_missing(precs, menu_packages):
    all_names = set(prec.name for prec in precs)
    for name in menu_packages:
        if name not in all_names:
            print("WARNING: no such package (in menu_packages): %s" % name)


def _copy_post_link_scripts_to_temp_env(link_list, env_dir, platform):
    prefix = "Scripts" if platform.startswith('win-') else "bin"
    ext = ".bat" if platform.startswith('win-') else ".sh"
    link_script_index = 0
    post_link_files = glob(os.path.join(env_dir, prefix, "*-post-link" + ext))
    for pkg in link_list:
        # this is what the post-link script should be named if it exists
        post_link_script = os.path.join(prefix, '.{}-post-link'.format(pkg['name']) + ext)
        if post_link_script in post_link_files:
            post_link_script_dir = os.path.join(env_dir, INSTALL_TMP_FOLDER, 'post-link')
            if not os.path.isdir(post_link_script_dir):
                os.makedirs(post_link_script_dir)
            # copy it in a numbered way, so that we establish the run order at install time
            dest_file = os.path.join(post_link_script_dir,
                                     "%03d-" % link_script_index + pkg['name'] + ext)
            shutil.copy2(os.path.join(env_dir, post_link_script), dest_file)
            link_script_index += 1


def _main(name, version, download_dir, platform, envdir, channel_urls=(),
          channels_remap=(), specs=(), menu_packages=(), verbose=True,
          dry_run=False, frozen_dir=None):

    # Append channels_remap srcs to channel_urls
    channel_urls = tuple(concatv(
        channel_urls,
        (x['src'] for x in channels_remap),
    ))

    if frozen_dir:
        env_path = frozen_dir
        package_link_order = []
    else:
        env_path = os.path.join(envdir, "_constructor_{}_{}".format(name, version))
        args = ["-p", env_path, '--json', '--force']
        for channel in channel_urls:
            args.extend(['-c', channel])

        if dry_run:
            args.append("--dry-run")
        args.extend(specs)
        print("Creating environment with arguments:")
        print(args)
        with env_vars({
            "CONDA_PKGS_DIRS": download_dir,
            "CONDA_SUBDIR": platform,
        }, callback=conda_reset_context):
            output = python_api.run_command("create", *args)
            package_link_order = json.loads(output[0]).get('actions', {}).get('LINK', [])

    if not dry_run:
        env_size = sum(os.path.getsize(os.path.join(dirpath, filename)) for
                       dirpath, dirnames, filenames in os.walk(env_path) for
                       filename in filenames)
    else:
        env_size = 0

    os.makedirs(os.path.join(env_path, INSTALL_TMP_FOLDER))

    # copies any post-link scripts into a install temp folder in the env
    #    within that folder, post-link scripts have a leading integer index
    #    according to their install order
    print("copying post-link scripts into sorted order")
    _copy_post_link_scripts_to_temp_env(package_link_order, env_path, platform)
    # detect and record and hard-coded prefixes.  We'll replace these at install time.
    print("Detecting hard-coded prefixes")
    prefix_api.detect_paths(env_path, out_path=os.path.join(env_path, INSTALL_TMP_FOLDER, 'has_prefix'))
    return env_path, env_size


def main(info, envdir, verbose=True, dry_run=False):
    name = info["name"]
    version = info["version"]
    download_dir = info["_download_dir"]
    platform = info["_platform"]
    channel_urls = info.get("channels", ())
    channels_remap = info.get('channels_remap', ())
    specs = info["specs"]
    frozen_dir = info.get('frozen_dir')

    if not channel_urls:
        sys.exit("Error: 'channels' is required")

    env_path, env_size = _main(
        name, version, download_dir, platform, envdir, channel_urls, channels_remap,
        specs, verbose, dry_run, frozen_dir)

    info["_env_size"] = env_size
    info["_env_path"] = env_path
