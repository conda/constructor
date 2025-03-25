# (c) 2016 Anaconda, Inc. / https://anaconda.com
# All Rights Reserved
#
# constructor is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.
"""
Application layer.

CLI logic and main functions to run constructor on a given input file.
"""

import argparse
import json
import logging
import os
import sys
from os.path import abspath, expanduser, isdir, join
from textwrap import dedent

from . import __version__
from .build_outputs import process_build_outputs
from .conda_interface import SUPPORTED_PLATFORMS, cc_platform
from .conda_interface import VersionOrder as Version
from .construct import SCHEMA_PATH, ns_platform
from .construct import parse as construct_parse
from .construct import verify as construct_verify
from .fcp import main as fcp_main
from .utils import StandaloneExe, identify_conda_exe, normalize_path, yield_lines

DEFAULT_CACHE_DIR = os.getenv("CONSTRUCTOR_CACHE", "~/.conda/constructor")

logger = logging.getLogger(__name__)


def get_installer_type(info):
    osname, unused_arch = info["_platform"].split("-")

    os_allowed = {"linux": ("sh",), "osx": ("sh", "pkg"), "win": ("exe",)}
    all_allowed = set(sum(os_allowed.values(), ("all",)))

    itype = info.get("installer_type")
    if not itype:
        return os_allowed[osname][:1]
    elif itype == "all":
        return os_allowed[osname]
    elif itype not in all_allowed:
        all_allowed = ", ".join(sorted(all_allowed))
        sys.exit("Error: invalid installer type '%s'; allowed: %s" % (itype, all_allowed))
    elif itype not in os_allowed[osname]:
        os_allowed = ", ".join(sorted(os_allowed[osname]))
        sys.exit(
            "Error: invalid installer type '%s' for %s; allowed: %s" % (itype, osname, os_allowed)
        )
    else:
        return (itype,)


def get_output_filename(info):
    try:
        return info["installer_filename"]
    except KeyError:
        pass

    osname, arch = info["_platform"].split("-")
    os_map = {"linux": "Linux", "osx": "MacOSX", "win": "Windows"}
    arch_name_map = {"64": "x86_64", "32": "x86"}
    ext = info["installer_type"]
    return "%s-%s-%s.%s" % (
        "%(name)s-%(version)s" % info,
        os_map.get(osname, osname),
        arch_name_map.get(arch, arch),
        ext,
    )


def main_build(
    dir_path,
    output_dir=".",
    platform=cc_platform,
    verbose=True,
    cache_dir=DEFAULT_CACHE_DIR,
    dry_run=False,
    conda_exe="conda.exe",
    config_filename="construct.yaml",
    debug=False,
):
    logger.info("platform: %s", platform)
    if not os.path.isfile(conda_exe):
        sys.exit("Error: Conda executable '%s' does not exist!" % conda_exe)
    cache_dir = abspath(expanduser(cache_dir))
    try:
        osname, unused_arch = platform.split("-")
    except ValueError:
        sys.exit("Error: invalid platform string '%s'" % platform)

    construct_path = join(dir_path, config_filename)
    info = construct_parse(construct_path, platform)
    construct_verify(info)
    info["CONSTRUCTOR_VERSION"] = __version__
    info["_input_dir"] = dir_path
    info["_output_dir"] = output_dir
    info["_platform"] = platform
    info["_download_dir"] = join(cache_dir, platform)
    info["_conda_exe"] = abspath(conda_exe)
    info["_debug"] = debug
    itypes = get_installer_type(info)

    if platform != cc_platform and "pkg" in itypes and not cc_platform.startswith("osx-"):
        sys.exit("Error: cannot construct a macOS 'pkg' installer on '%s'" % cc_platform)

    exe_type, exe_version = identify_conda_exe(info.get("_conda_exe"))
    if exe_version is not None:
        exe_version = Version(exe_version)
    info["_conda_exe_type"] = exe_type
    info["_conda_exe_version"] = exe_version
    if osname == "win" and exe_type == StandaloneExe.MAMBA:
        # TODO: Investigate errors on Windows and re-enable
        sys.exit("Error: micromamba is not supported on Windows installers.")

    if info.get("uninstall_with_conda_exe") and not (
        exe_type == StandaloneExe.CONDA and exe_version and exe_version >= Version("24.11.0")
    ):
        sys.exit("Error: uninstalling with conda.exe requires conda-standalone 24.11.0 or newer.")

    logger.debug("conda packages download: %s", info["_download_dir"])

    for key in ("welcome_image_text", "header_image_text"):
        if key not in info:
            info[key] = info["name"]

    for key in (
        "license_file",
        "welcome_image",
        "header_image",
        "icon_image",
        "pre_install",
        "post_install",
        "pre_uninstall",
        "environment_file",
        "nsis_template",
        "welcome_file",
        "readme_file",
        "conclusion_file",
        "signing_certificate",
        "post_install_pages",
    ):
        if value := info.get(key):  # only join if there's a truthy value set
            if isinstance(value, str):
                info[key] = abspath(join(dir_path, info[key]))
            elif isinstance(value, list):
                info[key] = [abspath(join(dir_path, val)) for val in value]

    # Normalize name and set default value
    if info.get("windows_signing_tool"):
        info["windows_signing_tool"] = info["windows_signing_tool"].lower().replace(".exe", "")
    elif info.get("signing_certificate"):
        info["windows_signing_tool"] = "signtool"

    for key in "specs", "packages", "virtual_specs":
        if key not in info:
            continue
        if isinstance(info[key], str):
            info[key] = list(yield_lines(join(dir_path, info[key])))

    # normalize paths to be copied; if they are relative, they must be to
    # construct.yaml's parent (dir_path)
    extras_types = ["extra_files", "temp_extra_files"]
    for extra_type in extras_types:
        extras = info.get(extra_type, ())
        new_extras = []
        for path in extras:
            if isinstance(path, str):
                new_extras.append(abspath(join(dir_path, path)))
            elif isinstance(path, dict):
                for orig, dest in path.items():
                    orig = abspath(join(dir_path, orig))
                    new_extras.append({orig: dest})
        info[extra_type] = new_extras

    for key in "channels", "specs", "exclude", "packages", "menu_packages", "virtual_specs":
        if key in info:
            # ensure strings in those lists are stripped
            info[key] = [line.strip() for line in info[key]]
            # ensure there are no empty strings
            if any((not s) for s in info[key]):
                sys.exit("Error: found empty element in '%s:'" % key)

    for env_name, env_config in info.get("extra_envs", {}).items():
        if env_name in ("base", "root"):
            raise ValueError(f"Environment name '{env_name}' cannot be used")
        for config_key, value in env_config.copy().items():
            if config_key == "environment_file":
                env_config[config_key] = abspath(join(dir_path, value))
            elif config_key == "channels_remap":
                env_config[config_key] = [
                    {"src": item["src"].strip(), "dest": item["dest"].strip()} for item in value
                ]
            elif isinstance(value, (list, tuple)):
                env_config[config_key] = [val.strip() for val in value]
            elif isinstance(value, str):
                env_config[config_key] = value.strip()
            else:
                env_config[config_key] = value

    # Installers will provide shortcut options and features only if the user
    # didn't opt-out by setting every `menu_packages` item to an empty list
    info["_enable_shortcuts"] = bool(
        info.get("menu_packages", True)
        or any(env.get("menu_packages", True) for env in info.get("extra_envs", {}).values())
    )
    if info["_enable_shortcuts"]:
        if exe_type is None or exe_version is None:
            logger.warning(
                "Could not identify conda-standalone / micromamba version. "
                "Will assume it is compatible with shortcuts."
            )
        elif sys.platform != "win32" and (
            exe_type != StandaloneExe.CONDA or (exe_version and exe_version < Version("23.11.0"))
        ):
            logger.warning("conda-standalone 23.11.0 or above is required for shortcuts on Unix.")
            info["_enable_shortcuts"] = "incompatible"

    # Add --no-rc option to CONDA_EXE command so that existing
    # .condarc files do not pollute the installation process.
    if exe_type == StandaloneExe.CONDA and exe_version and exe_version >= Version("24.9.0"):
        info["_ignore_condarcs_arg"] = "--no-rc"
    elif exe_type == StandaloneExe.MAMBA:
        info["_ignore_condarcs_arg"] = "--no-rc"
    else:
        info["_ignore_condarcs_arg"] = ""

    if "pkg" in itypes:
        if (domains := info.get("pkg_domains")) is not None:
            domains = {key: str(val).lower() for key, val in domains.items()}
            if str(domains.get("enable_localSystem", "")).lower() == "true" and not info.get(
                "default_location_pkg"
            ):
                logger.warning(
                    "enable_localSystem should not be enabled without setting"
                    " `default_location_pkg` to avoid installing directly "
                    " into the root directory."
                )
            info["pkg_domains"] = domains
        else:
            info["pkg_domains"] = {
                "enable_anywhere": "true",
                "enable_currentUserHome": "true",
            }

    info["installer_type"] = itypes[0]
    fcp_main(info, verbose=verbose, dry_run=dry_run, conda_exe=conda_exe)
    if dry_run:
        logger.info("Dry run, no installers or build outputs created.")
        return

    # info has keys
    # 'name', 'version', 'channels', 'exclude',
    # '_platform', '_download_dir', '_outpath'
    # 'specs': ['python 3.5*', 'conda', 'nomkl', 'numpy', 'scipy', 'pandas',
    #           'notebook', 'matplotlib', 'lighttpd']
    # 'license_file': '/Users/kfranz/continuum/constructor/examples/miniconda/EULA.txt'
    # '_dists': list[Dist]
    # '_urls': list[Tuple[url, md5]]

    os.makedirs(output_dir, exist_ok=True)
    info_dicts = []
    for itype in itypes:
        if itype == "sh":
            from .shar import create as shar_create

            create = shar_create
        elif itype == "pkg":
            from .osxpkg import create as osxpkg_create

            create = osxpkg_create
        elif itype == "exe":
            from .winexe import create as winexe_create

            create = winexe_create
        info["installer_type"] = itype
        info["_outpath"] = abspath(join(output_dir, get_output_filename(info)))
        create(info, verbose=verbose)
        if len(itypes) > 1:
            info_dicts.append(info.copy())
        logger.info("Successfully created '%(_outpath)s'.", info)

    # Merge info files for each installer type
    if len(itypes) > 1:
        keys = set()
        for info_dict in info_dicts:
            keys.update(info_dict.keys())
        for key in keys:
            if any(info_dict.get(key) != info.get(key) for info_dict in info_dicts):
                info[key] = [info_dict.get(key, "") for info_dict in info_dicts]

    process_build_outputs(info)


class _HelpConstructAction(argparse.Action):
    def __init__(
        self,
        option_strings,
        dest=argparse.SUPPRESS,
        default=argparse.SUPPRESS,
        help="describe available configuration options for construct.yaml files and exit",
    ):
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help,
        )

    def __call__(self, parser, namespace, values, option_string=None):
        parser._print_message(self._build_message(), sys.stdout)
        parser.exit()

    def _build_message(self):
        msg = dedent(
            """
            The 'construct.yaml' specification
            ==================================

            constructor version {version}

            The `construct.yaml` file is the primary mechanism for controlling
            the output of the Constructor package. The file contains a list of
            key/value pairs in the standard YAML format.

            Available keys
            --------------

            {available_keys}

            Available selectors
            -------------------
            Constructor can use the same Selector enhancement of the YAML format
            used in conda-build ('# [selector]'). Available keywords are:

            {available_selectors}
            """
        )
        available_keys = [f"> Check full details in {SCHEMA_PATH}", ""]
        schema = json.loads(SCHEMA_PATH.read_text())
        for name, prop in schema["properties"].items():
            if prop.get("deprecated"):
                continue
            available_keys.append(f"{name}")
            available_keys.append("·" * len(name))
            available_keys.append(prop.get("description", "No description found."))
            available_keys.append("")

        available_selectors = [f"- {sel}" for sel in sorted(ns_platform(sys.platform).keys())]
        return msg.format(
            version=__version__,
            available_keys="\n".join(available_keys),
            available_selectors="\n".join(available_selectors),
        )


def main():
    logging.basicConfig(level=logging.INFO)
    p = argparse.ArgumentParser(description="build an installer from <DIRECTORY>/construct.yaml")

    p.add_argument("--help-construct", action=_HelpConstructAction)

    p.add_argument("--debug", action="store_true")

    p.add_argument(
        "--output-dir",
        action="store",
        default=os.getcwd(),
        help="path to directory in which output installer is written "
        f"to, defaults to CWD ('{os.getcwd()}')",
        metavar="PATH",
    )

    p.add_argument(
        "--cache-dir",
        action="store",
        default=DEFAULT_CACHE_DIR,
        help="cache directory, used for downloading conda packages, "
        "may be changed by CONSTRUCTOR_CACHE, "
        f"defaults to '{DEFAULT_CACHE_DIR}'",
        metavar="PATH",
    )

    p.add_argument("--clean", action="store_true", help="clean out the cache directory and exit")

    p.add_argument(
        "--platform",
        action="store",
        default=cc_platform,
        help="the platform for which installer is for, "
        f"defaults to '{cc_platform}'. Options, e.g.: {SUPPORTED_PLATFORMS}",
    )

    p.add_argument(
        "--dry-run",
        help="solve package specs but do not create installer",
        default=False,
        action="store_true",
    )

    p.add_argument("-v", "--verbose", action="store_true")

    p.add_argument(
        "-V",
        "--version",
        help="display the version being used and exit",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    p.add_argument(
        "--conda-exe",
        help="path to conda executable (conda-standalone, micromamba)",
        action="store",
        metavar="CONDA_EXE",
    )

    p.add_argument(
        "--config-filename",
        help="path to construct YAML file ready by constructor",
        action="store",
        metavar="FILENAME",
        dest="config_filename",
        default="construct.yaml",
    )

    p.add_argument(
        "dir_path",
        help="directory containing construct.yaml",
        action="store",
        nargs="?",
        default=os.getcwd(),
        metavar="DIRECTORY",
    )

    args = p.parse_args()
    logger.info("Got the following cli arguments: '%s'", args)

    if args.verbose or args.debug:
        logging.getLogger("constructor").setLevel(logging.DEBUG)

    if args.clean:
        import shutil

        cache_dir = abspath(expanduser(args.cache_dir))
        logger.info("cleaning cache: '%s'", cache_dir)
        if isdir(cache_dir):
            shutil.rmtree(cache_dir)
        return

    dir_path = args.dir_path
    if not isdir(dir_path):
        p.error("no such directory: %s" % dir_path)
    if os.sep in args.config_filename:
        p.error("--config-filename can only be a filename, not a path")
    full_config_path = os.path.join(dir_path, args.config_filename)
    if not os.path.isfile(full_config_path):
        p.error("no such file: %s" % full_config_path)

    conda_exe = args.conda_exe
    conda_exe_default_path = os.path.join(sys.prefix, "standalone_conda", "conda.exe")
    conda_exe_default_path = normalize_path(conda_exe_default_path)
    if conda_exe:
        conda_exe = normalize_path(os.path.abspath(conda_exe))
    elif args.platform != cc_platform:
        p.error("setting --conda-exe is required for building a non-native installer")
    else:
        conda_exe = conda_exe_default_path
    if not os.path.isfile(conda_exe):
        if conda_exe != conda_exe_default_path:
            p.error("file not found: %s" % args.conda_exe)
        p.error(
            """
no standalone conda executable was found. The
easiest way to obtain one is to install the 'conda-standalone' package.
Alternatively, you can download an executable manually and supply its
path with the --conda-exe argument. Self-contained executables can be
downloaded from https://repo.anaconda.com/pkgs/misc/conda-execs/ and/or
https://github.com/conda/conda-standalone/releases""".lstrip()
        )

    out_dir = normalize_path(args.output_dir)
    main_build(
        dir_path,
        output_dir=out_dir,
        platform=args.platform,
        verbose=args.verbose,
        cache_dir=args.cache_dir,
        dry_run=args.dry_run,
        conda_exe=conda_exe,
        config_filename=args.config_filename,
        debug=args.debug,
    )


if __name__ == "__main__":
    main()
