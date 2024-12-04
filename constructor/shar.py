# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import logging
import os
import shlex
import shutil
import stat
import tarfile
import tempfile
from os.path import basename, dirname, getsize, isdir, join, relpath

from .construct import ns_platform
from .jinja import render_template
from .preconda import copy_extra_files
from .preconda import files as preconda_files
from .preconda import write_files as preconda_write_files
from .utils import (
    add_condarc,
    approx_size_kb,
    filename_dist,
    get_final_channels,
    hash_files,
    parse_virtual_specs,
    read_ascii_only,
    shortcuts_flags,
)

THIS_DIR = dirname(__file__)

logger = logging.getLogger(__name__)


def has_shebang(filename):
    with open(filename, "rb") as fp:
        return b"#!" == fp.read(2)


def make_executable(tarinfo):
    tarinfo.mode |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    return tarinfo


def read_header_template():
    path = join(THIS_DIR, 'header.sh')
    logger.info('Reading: %s', path)
    with open(path) as fi:
        return fi.read()


def get_header(conda_exec, tarball, info):
    name = info['name']

    has_license = bool(info.get('license_file'))
    variables = ns_platform(info['_platform'])
    variables['keep_pkgs'] = bool(info.get('keep_pkgs', False))
    variables['batch_mode'] = bool(info.get('batch_mode', False))
    variables['has_license'] = has_license
    if variables['batch_mode'] and has_license:
        raise Exception(
            "It is not possible to use both the 'batch_mode' and "
            "'license_file' options together."
        )
    for key in 'pre_install', 'post_install', 'pre_uninstall':
        variables['has_%s' % key] = bool(key in info)
        if key in info:
            variables['direct_execute_%s' % key] = has_shebang(info[key])
    variables['initialize_conda'] = info.get('initialize_conda', True)
    variables['initialize_by_default'] = info.get('initialize_by_default', False)
    variables['has_conda'] = info['_has_conda']
    variables['enable_shortcuts'] = str(info['_enable_shortcuts']).lower()
    variables['check_path_spaces'] = info.get("check_path_spaces", True)
    install_lines = list(add_condarc(info))
    # Omit __osx and __glibc because those are tested with shell code direcly
    virtual_specs = [
        spec
        for spec in info.get("virtual_specs", ())
        if "__osx" not in spec and "__glibc" not in spec
    ]
    variables['installer_name'] = name
    variables['installer_version'] = info['version']
    variables['installer_platform'] = info['_platform']
    variables['installer_md5'] = hash_files([conda_exec, tarball])
    variables['default_prefix'] = info.get('default_prefix', '${HOME:-/opt}/%s' % name.lower())
    variables['first_payload_size'] = getsize(conda_exec)
    variables['second_payload_size'] = getsize(tarball)
    variables['install_commands'] = '\n'.join(install_lines)
    variables['channels'] = ','.join(get_final_channels(info))
    variables['conclusion_text'] = info.get("conclusion_text", "installation finished.")
    variables['pycache'] = '__pycache__'
    variables['shortcuts'] = shortcuts_flags(info)
    variables['register_envs'] = str(info.get("register_envs", True)).lower()
    variables['total_installation_size_kb'] = str(approx_size_kb(info, "total"))
    variables['virtual_specs'] = shlex.join(virtual_specs)
    variables['no_rcs_arg'] = info.get('_ignore_condarcs_arg', '')
    if has_license:
        variables['license'] = read_ascii_only(info['license_file'])

    virtual_specs = parse_virtual_specs(info)
    min_osx_version = virtual_specs.get("__osx", {}).get("min") or ""
    variables['min_osx_version'] = min_osx_version
    min_glibc_version = virtual_specs.get("__glibc", {}).get("min") or ""
    variables['min_glibc_version'] = min_glibc_version

    variables['script_env_variables'] = '\n'.join(
        [f"export {key}='{value}'" for key, value in info.get('script_env_variables', {}).items()])

    return render_template(read_header_template(), **variables)


def create(info, verbose=False):
    tmp_dir_base_path = join(dirname(info['_outpath']), "tmp")
    try:
        os.makedirs(tmp_dir_base_path)
    except Exception:
        pass
    tmp_dir = tempfile.mkdtemp(dir=tmp_dir_base_path)
    preconda_write_files(info, tmp_dir)

    preconda_tarball = join(tmp_dir, 'preconda.tar.bz2')
    postconda_tarball = join(tmp_dir, 'postconda.tar.bz2')
    pre_t = tarfile.open(preconda_tarball, 'w:bz2')
    post_t = tarfile.open(postconda_tarball, 'w:bz2')
    for dist in preconda_files:
        fn = filename_dist(dist)
        pre_t.add(join(tmp_dir, fn), 'pkgs/' + fn)

    for env_name in info.get("_extra_envs_info", ()):
        pre_t.add(join(tmp_dir, "envs", env_name, "env.txt"),
                  f"pkgs/envs/{env_name}/env.txt")
        pre_t.add(join(tmp_dir, "envs", env_name, "shortcuts.txt"),
                  f"pkgs/envs/{env_name}/shortcuts.txt")

    for key in 'pre_install', 'post_install':
        if key in info:
            pre_t.add(info[key], 'pkgs/%s.sh' % key,
                      filter=make_executable if has_shebang(info[key]) else None)
    cache_dir = join(tmp_dir, 'cache')
    if isdir(cache_dir):
        for cf in os.listdir(cache_dir):
            if cf.endswith(".json"):
                pre_t.add(join(cache_dir, cf), 'pkgs/cache/' + cf)

    all_dists = info["_dists"].copy()
    for env_data in info.get("_extra_envs_info", {}).values():
        all_dists += env_data["_dists"]
    all_dists = list({dist: None for dist in all_dists})  # de-duplicate

    for dist in all_dists:
        if filename_dist(dist).endswith(".conda"):
            _dist = filename_dist(dist)[:-6]
        elif filename_dist(dist).endswith(".tar.bz2"):
            _dist = filename_dist(dist)[:-8]
        record_file = join(_dist, 'info', 'repodata_record.json')
        record_file_src = join(tmp_dir, record_file)
        record_file_dest = join('pkgs', record_file)
        pre_t.add(record_file_src, record_file_dest)
    pre_t.addfile(tarinfo=tarfile.TarInfo("conda-meta/history"))
    post_t.add(join(tmp_dir, 'conda-meta', 'history'), 'conda-meta/history')

    for env_name in info.get("_extra_envs_info", {}):
        pre_t.addfile(tarinfo=tarfile.TarInfo(f"envs/{env_name}/conda-meta/history"))
        post_t.add(join(tmp_dir, 'envs', env_name, 'conda-meta', 'history'),
                   f"envs/{env_name}/conda-meta/history")

    extra_files = copy_extra_files(info.get("extra_files", []), tmp_dir)
    for path in extra_files:
        post_t.add(path, relpath(path, tmp_dir))

    pre_t.close()
    post_t.close()

    tarball = join(tmp_dir, 'tmp.tar')
    t = tarfile.open(tarball, 'w')
    t.add(preconda_tarball, basename(preconda_tarball))
    t.add(postconda_tarball, basename(postconda_tarball))
    if 'license_file' in info:
        t.add(info['license_file'], 'LICENSE.txt')
    for dist in all_dists:
        fn = filename_dist(dist)
        t.add(join(info['_download_dir'], fn), 'pkgs/' + fn)
    t.close()

    conda_exec = info["_conda_exe"]
    header = get_header(conda_exec, tarball, info)
    shar_path = info['_outpath']
    with open(shar_path, 'wb') as fo:
        fo.write(header.encode('utf-8'))
        for payload in [conda_exec, tarball]:
            with open(payload, 'rb') as fi:
                while True:
                    chunk = fi.read(262144)
                    if not chunk:
                        break
                    fo.write(chunk)

    os.unlink(tarball)
    os.chmod(shar_path, 0o755)
    if not info.get('_debug'):
        shutil.rmtree(tmp_dir)
