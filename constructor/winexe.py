# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.
"""
Logic to build the EXE installers for Windows, with NSIS.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
import tempfile
from os.path import abspath, basename, dirname, isfile, join
from pathlib import Path
from subprocess import check_output, run

from .construct import ns_platform
from .imaging import write_images
from .jinja import render_template
from .preconda import copy_extra_files
from .preconda import write_files as preconda_write_files
from .signing import AzureSignTool, WindowsSignTool
from .utils import (
    add_condarc,
    approx_size_kb,
    copy_conda_exe,
    filename_dist,
    get_final_channels,
    make_VIProductVersion,
    shortcuts_flags,
    win_str_esc,
)

NSIS_DIR = join(abspath(dirname(__file__)), "nsis")
MAKENSIS_EXE = abspath(join(sys.prefix, "NSIS", "makensis.exe"))

logger = logging.getLogger(__name__)


def read_nsi_tmpl(info) -> str:
    path = abspath(info.get("nsis_template", join(NSIS_DIR, "main.nsi.tmpl")))
    logger.info("Reading: %s", path)
    with open(path) as fi:
        return fi.read()


def get_extra_files(paths, common_parent):
    paths = sorted([Path(p) for p in paths])
    extra_files = {}
    for path in paths:
        relative_parent = path.relative_to(common_parent).parent
        output_path = f"$INSTDIR\\{relative_parent}"
        if output_path not in extra_files:
            extra_files[output_path] = []
        extra_files[output_path].append(str(path))
    return extra_files


def custom_nsi_insert_from_file(filepath: os.PathLike) -> str:
    """Insert NSI script commands from file.

    Args:
        filepath (os.PathLike): Path to file

    Returns:
        string block of file
    """
    if not filepath:
        return ""
    return Path(filepath).read_text()


def setup_envs_commands(info, dir_path):
    environments = []
    # set up the base environment
    environments.append(
        {
            "name": "base",
            "prefix": r"$INSTDIR",
            # initial-state.explicit.txt as seen by the running installer
            "lockfile_txt": r"$INSTDIR\conda-meta\initial-state.explicit.txt",
            # initial-state.explicit.txt path while building the installer
            "lockfile_txt_abspath": join(dir_path, "conda-meta", "initial-state.explicit.txt"),
            "conda_meta": r"$INSTDIR\conda-meta",
            "history_abspath": join(dir_path, "conda-meta", "history"),
            "final_channels": get_final_channels(info),
            "shortcuts": shortcuts_flags(info),
            "register_envs": str(info.get("register_envs", True)).lower(),
            "no_rcs_arg": info.get("_ignore_condarcs_arg", ""),
        }
    )
    # now we generate one item per extra env, if present
    for env_name in info.get("_extra_envs_info", {}):
        env_info = info["extra_envs"][env_name]
        # Needed for shortcuts_flags function
        if "_conda_exe_type" not in env_info:
            env_info["_conda_exe_type"] = info.get("_conda_exe_type")
        channel_info = {
            "channels": env_info.get("channels", info.get("channels", ())),
            "channels_remap": env_info.get("channels_remap", info.get("channels_remap", ())),
        }
        environments.append(
            {
                "name": env_name,
                "prefix": join("$INSTDIR", "envs", env_name),
                "lockfile_txt": join(
                    "$INSTDIR", "envs", env_name, "conda-meta", "initial-state.explicit.txt"
                ),
                "lockfile_txt_abspath": join(
                    dir_path, "envs", env_name, "conda-meta", "initial-state.explicit.txt"
                ),
                "conda_meta": join("$INSTDIR", "envs", env_name, "conda-meta"),
                "history_abspath": join(dir_path, "envs", env_name, "conda-meta", "history"),
                "final_channels": get_final_channels(channel_info),
                "shortcuts": shortcuts_flags(env_info),
                "register_envs": str(info.get("register_envs", True)).lower(),
                "no_rcs_arg": info.get("_ignore_condarcs_arg", ""),
            }
        )

    return environments


def make_nsi(
    info: dict,
    dir_path: str,
    extra_files: list = None,
    temp_extra_files: list = None,
    signing_tool: AzureSignTool | WindowsSignTool = None,
):
    "Creates the tmp/main.nsi from the template file"

    if extra_files is None:
        extra_files = []
    if temp_extra_files is None:
        temp_extra_files = []
    name = info["name"]
    download_dir = info["_download_dir"]

    dists = info["_dists"].copy()
    for env_info in info["_extra_envs_info"].values():
        dists += env_info["_dists"]
    dists = list({dist: None for dist in dists})  # de-duplicate

    arch = int(info["_platform"].split("-")[1])
    info["pre_install_desc"] = info.get("pre_install_desc", "")
    info["post_install_desc"] = info.get("post_install_desc", "")

    variables = {
        "installer_name": name,
        "installer_version": info["version"],
        "company": info.get("company", "Unknown, Inc."),
        "installer_platform": info["_platform"],
        "arch": "%d-bit" % arch,
        "default_prefix": info.get("default_prefix", join("%USERPROFILE%", name.lower())),
        "default_prefix_domain_user": info.get(
            "default_prefix_domain_user", join("%LOCALAPPDATA%", name.lower())
        ),
        "default_prefix_all_users": info.get(
            "default_prefix_all_users", join("%ALLUSERSPROFILE%", name.lower())
        ),
        "pre_install_desc": info["pre_install_desc"],
        "post_install_desc": info["post_install_desc"],
        "enable_shortcuts": "yes" if info["_enable_shortcuts"] is True else "no",
        "show_register_python": "yes" if info.get("register_python", True) else "no",
        "show_add_to_path": info.get("initialize_conda", "classic") or "no",
        "outfile": info["_outpath"],
        "vipv": make_VIProductVersion(info["version"]),
        "constructor_version": info["CONSTRUCTOR_VERSION"],
        # @-prefixed paths point to {dir_path}
        "iconfile": "@icon.ico",
        "headerimage": "@header.bmp",
        "welcomeimage": "@welcome.bmp",
        "licensefile": abspath(info.get("license_file", join(NSIS_DIR, "placeholder_license.txt"))),
        "conda_history": "@" + join("conda-meta", "history"),
        "conda_exe": "@_conda.exe",
        "urls_file": "@" + join("pkgs", "urls"),
        "urls_txt_file": "@" + join("pkgs", "urls.txt"),
        "pre_install": "@pre_install.bat",
        "post_install": "@post_install.bat",
        "pre_uninstall": "@pre_uninstall.bat",
        "index_cache": "@" + join("pkgs", "cache"),
        "repodata_record": "@" + join("pkgs", "repodata_record.json"),
    }

    conclusion_text = info.get("conclusion_text", "")
    if conclusion_text:
        conclusion_lines = conclusion_text.strip().splitlines()
        variables["conclusion_title"] = conclusion_lines[0].strip()
        # See https://nsis.sourceforge.io/Docs/Modern%20UI/Readme.html#toggle_pgf
        # for the newlines business
        variables["conclusion_text"] = "\r\n".join(conclusion_lines[1:])

    for key in ["welcome_file", "conclusion_file", "post_install_pages"]:
        value = info.get(key, "")
        if not value:
            continue
        if isinstance(value, str) and not value.endswith(".nsi"):
            logger.warning(
                "On Windows, %s must be an .nsi file; %s will be ignored.",
                key,
                value,
            )
        elif isinstance(value, list):
            valid_values = []
            for val in value:
                if val.endswith(".nsi"):
                    valid_values.append(val)
                else:
                    logger.warning(
                        "On Windows, %s must be .nsi files; %s will be ignored.",
                        key,
                        val,
                    )
                info[key] = valid_values

    for key, value in variables.items():
        if isinstance(value, str) and value.startswith("@"):
            value = join(dir_path, value[1:])
        variables[key] = win_str_esc(value)

    # From now on, the items added to variables will NOT be escaped

    # These are mostly booleans we use with if-checks
    default_uninstall_name = "${NAME} ${VERSION}"
    variables["has_python"] = False
    for dist in dists:
        py_name, py_version, _ = filename_dist(dist).rsplit("-", 2)
        if py_name == "python":
            variables["has_python"] = True
            variables["pyver_components"] = py_version.split(".")
            break

    if variables["has_python"]:
        variables["register_python"] = info.get("register_python", True)
        variables["register_python_default"] = info.get("register_python_default", None)
        default_uninstall_name += " (Python ${PYVERSION} ${ARCH})"
    else:
        variables["register_python"] = False
        variables["register_python_default"] = None

    variables.update(ns_platform(info["_platform"]))
    variables["initialize_conda"] = info.get("initialize_conda", "classic")
    variables["initialize_by_default"] = info.get("initialize_by_default", None)
    variables["check_path_length"] = info.get("check_path_length", False)
    variables["check_path_spaces"] = info.get("check_path_spaces", True)
    variables["keep_pkgs"] = info.get("keep_pkgs") or False
    variables["pre_install_exists"] = bool(info.get("pre_install"))
    variables["post_install_exists"] = bool(info.get("post_install"))
    variables["with_conclusion_text"] = bool(conclusion_text)
    variables["enable_debugging"] = bool(os.environ.get("NSIS_USING_LOG_BUILD"))
    variables["has_conda"] = info["_has_conda"]
    variables["custom_welcome"] = info.get("welcome_file", "").endswith(".nsi")
    variables["custom_conclusion"] = info.get("conclusion_file", "").endswith(".nsi")
    variables["has_license"] = bool(info.get("license_file"))
    variables["uninstall_with_conda_exe"] = bool(info.get("uninstall_with_conda_exe"))
    variables["needs_python_exe"] = info.get("_win_install_needs_python_exe", True)

    approx_pkgs_size_kb = approx_size_kb(info, "pkgs")

    # UPPERCASE variables are unescaped (and unquoted)
    variables["CONDA_LOG_ARG"] = (
        '--log-file "${STEP_LOG}"' if info.get("_conda_exe_supports_logging") else ""
    )
    variables["NAME"] = name
    variables["NSIS_DIR"] = NSIS_DIR
    variables["BITS"] = str(arch)
    variables["DISTS"] = [win_str_esc(join(download_dir, dist)) for dist in dists]
    variables["SIGNTOOL_COMMAND"] = signing_tool.get_signing_command() if signing_tool else ""
    variables["SETUP_ENVS"] = setup_envs_commands(info, dir_path)
    variables["WRITE_CONDARC"] = list(add_condarc(info))
    variables["SIZE"] = approx_pkgs_size_kb
    variables["UNINSTALL_NAME"] = info.get("uninstall_name", default_uninstall_name)
    variables["EXTRA_FILES"] = get_extra_files(extra_files, dir_path)
    variables["SCRIPT_ENV_VARIABLES"] = {
        key: win_str_esc(val) for key, val in info.get("script_env_variables", {}).items()
    }
    variables["CUSTOM_WELCOME_FILE"] = (
        custom_nsi_insert_from_file(info.get("welcome_file", ""))
        if variables["custom_welcome"]
        else ""
    )
    variables["CUSTOM_CONCLUSION_FILE"] = (
        custom_nsi_insert_from_file(info.get("conclusion_file", ""))
        if variables["custom_conclusion"]
        else ""
    )
    if isinstance(info.get("post_install_pages"), str):
        variables["POST_INSTALL_PAGES"] = [custom_nsi_insert_from_file(info["post_install_pages"])]
    else:
        variables["POST_INSTALL_PAGES"] = [
            custom_nsi_insert_from_file(file) for file in info.get("post_install_pages", [])
        ]
    variables["TEMP_EXTRA_FILES"] = sorted(temp_extra_files, key=Path)
    variables["VIRTUAL_SPECS"] = " ".join([f'"{spec}"' for spec in info.get("virtual_specs", ())])
    # This is the same but without quotes so we can print it fine
    variables["VIRTUAL_SPECS_DEBUG"] = " ".join([spec for spec in info.get("virtual_specs", ())])
    variables["LICENSEFILENAME"] = basename(info.get("license_file", "placeholder_license.txt"))
    variables["NO_RCS_ARG"] = info.get("_ignore_condarcs_arg", "")

    data = render_template(read_nsi_tmpl(info), **variables)
    if info["_platform"].startswith("win") and sys.platform != "win32":
        # Branding /TRIM commannd is unsupported on non win platform
        data_lines = data.split("\n")
        for i, line in enumerate(data_lines):
            if "/TRIM" in line:
                del data_lines[i]
                break
        data = "\n".join(data_lines)

    nsi_path = join(dir_path, "main.nsi")
    with open(nsi_path, "w") as fo:
        fo.write(data)
    # Uncomment to see the file for debugging
    # with open('main.nsi', 'w') as fo:
    #     fo.write(data)
    # Copy all the NSIS header files (*.nsh)
    for fn in os.listdir(NSIS_DIR):
        if fn.endswith(".nsh"):
            shutil.copy(join(NSIS_DIR, fn), join(dir_path, fn))

    logger.info("Created %s file", nsi_path)
    return nsi_path


def verify_nsis_install():
    logger.info("Checking for '%s'", MAKENSIS_EXE)
    if not isfile(MAKENSIS_EXE):
        sys.exit(
            """
Error: no file %s
    please make sure nsis is installed:
    > conda install nsis
"""
            % MAKENSIS_EXE
        )
    if sys.platform == "win32":
        out = check_output([MAKENSIS_EXE, "/VERSION"])
    else:
        out = check_output([MAKENSIS_EXE, "-VERSION"])
    out = out.decode("utf-8").strip()
    logger.info("NSIS version: %s", out)
    for dn in "x86-unicode", "x86-ansi", ".":
        untgz_dll = abspath(join(sys.prefix, "NSIS", "Plugins", dn, "untgz.dll"))
        if isfile(untgz_dll):
            break
    else:
        sys.exit("Error: no file untgz.dll")


def create(info, verbose=False):
    verify_nsis_install()
    signing_tool = None
    if signing_tool_name := info.get("windows_signing_tool"):
        if signing_tool_name == "signtool":
            signing_tool = WindowsSignTool(certificate_file=info.get("signing_certificate"))
        elif signing_tool_name == "azuresigntool":
            signing_tool = AzureSignTool()
        else:
            raise ValueError(f"Unknown signing tool: {signing_tool_name}")
        signing_tool.verify_signing_tool()
    tmp_dir = tempfile.mkdtemp()
    preconda_write_files(info, tmp_dir)
    copied_extra_files = copy_extra_files(info.get("extra_files", []), tmp_dir)
    copied_temp_extra_files = copy_extra_files(info.get("temp_extra_files", []), tmp_dir)
    extra_conda_exe_files = copy_conda_exe(tmp_dir, "_conda.exe", info["_conda_exe"])

    pre_dst = join(tmp_dir, "pre_install.bat")
    pre_install_script = info.get("pre_install")
    if pre_install_script:
        shutil.copy(pre_install_script, pre_dst)

    post_dst = join(tmp_dir, "post_install.bat")
    try:
        shutil.copy(info["post_install"], post_dst)
    except KeyError:
        with open(post_dst, "w") as fo:
            fo.write(":: this is an empty post install .bat script\n")

    preun_dst = join(tmp_dir, "pre_uninstall.bat")
    try:
        shutil.copy(info["pre_uninstall"], preun_dst)
    except KeyError:
        with open(preun_dst, "w") as fo:
            fo.write(":: this is an empty pre uninstall .bat script\n")

    write_images(info, tmp_dir)
    nsi = make_nsi(
        info,
        tmp_dir,
        extra_files=extra_conda_exe_files + copied_extra_files,
        temp_extra_files=copied_temp_extra_files,
        signing_tool=signing_tool,
    )
    verbosity = f"{'/' if sys.platform == 'win32' else '-'}V{4 if verbose else 2}"
    args = [MAKENSIS_EXE, verbosity, nsi]
    logger.info("Calling: %s", args)
    process = run(args, capture_output=True, text=True)
    if process.returncode:
        logger.info("makensis stdout:\n'%s'", process.stdout)
        logger.error("makensis stderr:\n'%s'", process.stderr)
        sys.exit(f"Failed to run {args}. Exit code: {process.returncode}.")
    else:
        logger.debug("makensis stdout:\n'%s'", process.stdout)
        logger.debug("makensis stderr:\n'%s'", process.stderr)

    if signing_tool:
        signing_tool.verify_signature(info["_outpath"])

    if not info.get("_debug"):
        shutil.rmtree(tmp_dir)


if __name__ == "__main__":
    make_nsi(
        {
            "name": "Maxi",
            "version": "1.2",
            "_platform": "win-64",
            "_outpath": "dummy.exe",
            "_download_dir": "dummy",
            "_dists": ["python-2.7.9-0.tar.bz2", "vs2008_runtime-1.0-1.tar.bz2"],
        },
        ".",
    )
