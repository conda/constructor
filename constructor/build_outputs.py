"""
Additional artifacts to be produced after building the installer.

Update documentation in `construct.py` if any changes are made.
"""

import json
import logging
import os
from collections import defaultdict
from pathlib import Path

from conda.base.constants import UNKNOWN_CHANNEL
from conda.common.url import remove_auth, split_anaconda_token
from conda.core.prefix_data import PrefixData, PrefixGraph
from conda.exports import default_prefix

from . import __version__
from ._schema import BuildOutputs
from .conda_interface import VersionOrder
from .utils import hash_files

logger = logging.getLogger(__name__)


def get_build_env_records(prefix=None):
    """Return the package records for the environment building the installer.

    Defaults to the currently active conda environment (`default_prefix`,
    i.e. the one running constructor) if no prefix is given. Not to be
    confused with construct.yaml's unrelated `default_prefix` setting,
    which is the end user's install location.
    """
    if prefix is None:
        prefix = default_prefix

    # Define a set of keys that we don't need to include in info.json.
    # The result of excluding these is a much smaller info.json (up to 70x).
    to_exclude = (
        "extracted_package_dir",
        "files",
        "link",
        "package_tarball_full_path",
        "paths_data",
    )
    # interoperability=True also picks up pip-installed packages, not just conda ones.
    prefix_records = PrefixData(prefix, interoperability=True).iter_records()
    return [
        {k: v for k, v in record.dump().items() if k not in to_exclude} for record in prefix_records
    ]


def _validate_output(output):
    if isinstance(output, str):
        output = {output: None}
    if not isinstance(output, dict):
        raise ValueError("'build_outputs' must be a list of str or a list of dicts.")
    if len(output) > 1:
        raise ValueError("'build_outputs' dicts can only have one key.")
    return {key: (value or {}) for (key, value) in output.items()}


def _needed_hash_algorithms(info: dict) -> set[str]:
    """Return hash algorithms required by the requested build outputs."""
    algorithms = set()

    for output in info.get("build_outputs", ()):
        output = _validate_output(output)
        name, config = output.popitem()

        if name == BuildOutputs.INFO_JSON:
            algorithms.add("sha256")
        elif name == BuildOutputs.HASH:
            algorithm = config.get("algorithm")
            if isinstance(algorithm, str):
                algorithms.add(algorithm)
            elif algorithm:
                algorithms.update(algorithm)

    return algorithms


def process_build_outputs(info: dict):
    algorithms = _needed_hash_algorithms(info)

    if algorithms:
        info["_installer_hashes"] = hash_files(
            [info["_outpath"]],
            algorithms,
        )

    for output in info.get("build_outputs", ()):
        output = _validate_output(output)

        name, config = output.popitem()

        handler = OUTPUT_HANDLERS.get(name)
        if not handler:
            raise ValueError(
                f"'build_outputs' key {name} is not recognized! "
                f"Available keys: {tuple(OUTPUT_HANDLERS.keys())}"
            )

        outpath = handler(info, **config)
        if outpath:
            logger.info("build_outputs: '%s' created '%s'.", name, outpath)


def dump_hash(info: dict, algorithm: str | None = None):
    if not algorithm:
        logger.warning("`hash` requires an algorithm. No hash files will be output.")
        return ""

    if isinstance(algorithm, str):
        algorithms = [algorithm]
    else:
        algorithms = algorithm

    installer = Path(info["_outpath"])
    outpaths = []

    for algo in algorithms:
        try:
            filehash = info["_installer_hashes"][algo]
        except KeyError:
            raise RuntimeError(
                f"Hash for algorithm '{algo}' not found. "
                f"Available algorithms: {', '.join(info.get('_installer_hashes', {}).keys())}"
            ) from None
        outpath = Path(f"{installer}.{algo}")

        with open(outpath, "w", newline="\n") as f:
            f.write(f"{filehash}  {installer.name}\n")

        outpaths.append(str(outpath.absolute()))

    return ", ".join(outpaths)


def dump_info(info):
    def _serialize(obj):
        if hasattr(obj, "dump"):
            return obj.dump()
        elif isinstance(obj, VersionOrder):
            return obj.norm_version
        else:
            return repr(obj)

    # Packages installed in the environment running constructor.
    info["_build_environment_packages"] = get_build_env_records()
    outpath = os.path.join(info["_output_dir"], "info.json")
    with open(outpath, "w") as f:
        json.dump(info, f, indent=2, default=_serialize)
    return os.path.abspath(outpath)


def dump_packages_list(info, env="base"):
    if env == "base":
        dists = info["_dists"]
    elif env in info["_extra_envs_info"]:
        dists = info["_extra_envs_info"][env]["_dists"]
    else:
        raise ValueError(f"env='{env}' is not a valid env name.")

    outpath = os.path.join(info["_output_dir"], f"pkg-list.{env}.txt")
    with open(outpath, "w") as fo:
        fo.write(f"# {info['name']} {info['version']}, env={env}\n")
        fo.write("\n".join(dists))
    return os.path.abspath(outpath)


def dump_lockfile(info, env="base"):
    if env == "base":
        records = info["_records"]
    elif env in info["_extra_envs_info"]:
        records = info["_extra_envs_info"][env]["_records"]
    else:
        raise ValueError(f"env='{env}' is not a valid env name.")
    lines = [
        "# This file may be used to create an environment using:",
        "# $ conda create --name <env> --file <this file>",
        f"# installer-name: {info['name']}",
        f"# installer-version: {info['version']}",
        f"# env-name: {env}",
        f"# platform: {info['_platform']}",
        f"# created-by: constructor {__version__}",
        "@EXPLICIT",
    ]
    for record in PrefixGraph(records).graph:
        url = record.get("url")
        if not url or url.startswith(UNKNOWN_CHANNEL):
            print("# no URL for: {}".format(record["fn"]))
            continue
        url = remove_auth(split_anaconda_token(url)[0])
        hash_value = record.get("md5")
        lines.append(url + (f"#{hash_value}" if hash_value else ""))

    outpath = os.path.join(info["_output_dir"], f"lockfile.{env}.txt")
    with open(outpath, "w") as f:
        f.write("\n".join(lines))
    return os.path.abspath(outpath)


def dump_licenses(info, include_text=False, text_errors=None):
    """
    Create a JSON document with a mapping with schema:

    {
        PackageRecord.dist_str(): {
            "type": str, # the license identifier
            "files: [
                {
                    "path": str,
                    "text": Optional[str],
                },
                ...
            ]
        },
        ...
    }

    Args:
        include_text: bool
            Whether to copy the contents of each license file in the JSON document,
            under .*.files[].text.
        text_errors: str or None
            How to handle decoding errors when reading the license text. Only relevant
            if include_text is True. Any str accepted by open()'s 'errors' argument is
            valid. See https://docs.python.org/3/library/functions.html#open.
    """
    licenses = defaultdict(dict)
    for pkg_record in info["_all_pkg_records"]:
        extracted_package_dir = pkg_record.extracted_package_dir
        licenses_dir = os.path.join(extracted_package_dir, "info", "licenses")
        licenses[pkg_record.dist_str()]["type"] = pkg_record.license
        licenses[pkg_record.dist_str()]["files"] = license_files = []
        if not os.path.isdir(licenses_dir):
            continue

        for directory, _, files in os.walk(licenses_dir):
            for filepath in files:
                license_path = os.path.join(directory, filepath)
                license_file = {"path": license_path, "text": None}
                if include_text:
                    license_file["text"] = Path(license_path).read_text(errors=text_errors)
                license_files.append(license_file)

    outpath = os.path.join(info["_output_dir"], "licenses.json")
    with open(outpath, "w") as f:
        json.dump(licenses, f, indent=2, default=repr)
    return os.path.abspath(outpath)


OUTPUT_HANDLERS = {
    "hash": dump_hash,
    "info.json": dump_info,
    "pkgs_list": dump_packages_list,
    "lockfile": dump_lockfile,
    "licenses": dump_licenses,
}
