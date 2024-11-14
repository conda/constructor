"""
Additional artifacts to be produced after building the installer.

Update documentation in `construct.py` if any changes are made.
"""
import hashlib
import json
import logging
import os
from collections import defaultdict
from pathlib import Path

from conda.base.constants import UNKNOWN_CHANNEL
from conda.common.url import remove_auth, split_anaconda_token

from . import __version__

logger = logging.getLogger(__name__)


def _validate_output(output):
    if isinstance(output, str):
        output = {output: None}
    if not isinstance(output, dict):
        raise ValueError("'build_outputs' must be a list of str or a list of dicts.")
    if len(output) > 1:
        raise ValueError("'build_outputs' dicts can only have one key.")
    return {key: (value or {}) for (key, value) in output.items()}


def process_build_outputs(info):
    for output in info.get("build_outputs", ()):
        output = _validate_output(output)
        name, config = output.popitem()
        handler = OUTPUT_HANDLERS.get(name)
        if not handler:
            raise ValueError(
                f"'output_builds' key {name} is not recognized! "
                f"Available keys: {tuple(OUTPUT_HANDLERS.keys())}"
            )
        outpath = handler(info, **config)
        logger.info("build_outputs: '%s' created '%s'.", name, outpath)


def dump_hash(info, algorithm=None):
    algorithm = algorithm or []
    if isinstance(algorithm, str):
        algorithm = [algorithm]
    algorithms = set(algorithm)
    if any(algo not in hashlib.algorithms_available for algo in algorithms):
        invalid = algorithms.difference(set(hashlib.algorithms_available))
        raise ValueError(f"Invalid algorithm: {', '.join(invalid)}")
    BUFFER_SIZE = 65536
    if isinstance(info["_outpath"], str):
        installers = [Path(info["_outpath"])]
    else:
        installers = [Path(outpath) for outpath in info["_outpath"]]
    outpaths = []
    for installer in installers:
        filehashes = {algo: hashlib.new(algo) for algo in algorithms}
        with open(installer, "rb") as f:
            while buffer := f.read(BUFFER_SIZE):
                for algo in algorithms:
                    filehashes[algo].update(buffer)
        for algo, filehash in filehashes.items():
            outpath = Path(f"{installer}.{algo}")
            outpath.write_text(f"{filehash.hexdigest()}  {installer.name}\n")
            outpaths.append(str(outpath.absolute()))
    return ", ".join(outpaths)


def dump_info(info):
    outpath = os.path.join(info["_output_dir"], "info.json")
    with open(outpath, "w") as f:
        json.dump(info, f, indent=2, default=repr)
    return os.path.abspath(outpath)


def dump_packages_list(info, env="base"):
    if env == "base":
        dists = info["_dists"]
    elif env in info["_extra_envs_info"]:
        dists = info["_extra_envs_info"][env]["_dists"]
    else:
        raise ValueError(f"env='{env}' is not a valid env name.")

    outpath = os.path.join(info["_output_dir"], f'pkg-list.{env}.txt')
    with open(outpath, 'w') as fo:
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
        f"# installer-name: {info['name']}"
        f"# installer-version: {info['version']}"
        f"# env-name: {env}"
        f"# platform: {info['_platform']}",
        f"# created-by: constructor {__version__}",
        "@EXPLICIT"
    ]
    for record in records:
        url = record.get("url")
        if not url or url.startswith(UNKNOWN_CHANNEL):
            print("# no URL for: {}".format(record["fn"]))
            continue
        url = remove_auth(split_anaconda_token(url)[0])
        hash_value = record.get("md5")
        lines.append(url + (f"#{hash_value}" if hash_value else ""))

    outpath = os.path.join(info["_output_dir"], f'lockfile.{env}.txt')
    with open(outpath, 'w') as f:
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
