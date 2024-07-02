"""
Additional artifacts to be produced after building the installer.

Update documentation in `construct.py` if any changes are made.
"""
import hashlib
import json
import logging
from collections import defaultdict
from pathlib import Path

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


def dump_hash(info, algorithm=""):
    if algorithm not in hashlib.algorithms_available:
        raise ValueError(f"Invalid algorithm: {', '.join(algorithm)}")
    BUFFER_SIZE = 65536
    if isinstance(info["_outpath"], str):
        installers = [Path(info["_outpath"])]
    else:
        installers = [Path(outpath) for outpath in info["_outpath"]]
    outpaths = []
    for installer in installers:
        filehash = hashlib.new(algorithm)
        with open(installer, "rb") as f:
            while buffer := f.read(BUFFER_SIZE):
                filehash.update(buffer)
        outpath = Path(f"{installer}.{algorithm}")
        outpath.write_text(f"{filehash.hexdigest()}  {installer.name}\n")
        outpaths.append(str(outpath.absolute()))
    return ", ".join(outpaths)


def dump_info(info):
    outpath = Path(info["_output_dir"], "info.json")
    outpath.write_text(json.dumps(info, indent=2, default=repr) + "\n")
    return outpath.absolute()


def dump_packages_list(info, env="base"):
    if env == "base":
        dists = info["_dists"]
    elif env in info["_extra_envs_info"]:
        dists = info["_extra_envs_info"][env]["_dists"]
    else:
        raise ValueError(f"env='{env}' is not a valid env name.")

    outpath = Path(info["_output_dir"], f'pkg-list.{env}.txt')
    outpath.write_text(f"# {info['name']} {info['version']}, env={env}\n")
    outpath.write_text("\n".join(dists))
    return outpath.absolute()


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
        licenses_dir = Path(extracted_package_dir, "info", "licenses")
        licenses[pkg_record.dist_str()]["type"] = pkg_record.license
        licenses[pkg_record.dist_str()]["files"] = license_files = []
        if not licenses_dir.is_dir():
            continue

        for directory, _, files in licenses_dir.walk():
            for filepath in files:
                license_path = directory / filepath
                license_file = {"path": license_path, "text": None}
                if include_text:
                    license_file["text"] = license_path.read_text(errors=text_errors)
                license_files.append(license_file)

    outpath = Path(info["_output_dir"], "licenses.json")
    outpath.write_text(json.dumps(licenses, indent=2, default=repr) + "\n")
    return outpath.absolute()


OUTPUT_HANDLERS = {
    "hash": dump_hash,
    "info.json": dump_info,
    "pkgs_list": dump_packages_list,
    "licenses": dump_licenses,
}
