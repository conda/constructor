"""
Logic to build installers using Briefcase.
"""

import logging
import re
import shutil
import sysconfig
import tempfile
from pathlib import Path
from subprocess import run

import tomli_w

from . import preconda
from .utils import DEFAULT_REVERSE_DOMAIN_ID, copy_conda_exe, filename_dist

BRIEFCASE_DIR = Path(__file__).parent / "briefcase"
EXTERNAL_PACKAGE_PATH = "external"

logger = logging.getLogger(__name__)


def get_name_version(info):
    name = info["name"]
    if not name:
        raise ValueError("Name is empty")

    # Briefcase requires version numbers to be in the canonical Python format, and some
    # installer types use the version to distinguish between upgrades, downgrades and
    # reinstalls. So try to produce a consistent ordering by extracting the last valid
    # version from the Constructor version string.
    #
    # Hyphens aren't allowed in this format, but for compatibility with Miniconda's
    # version format, we treat them as dots.
    matches = list(
        re.finditer(
            r"(\d+!)?\d+(\.\d+)*((a|b|rc)\d+)?(\.post\d+)?(\.dev\d+)?",
            info["version"].lower().replace("-", "."),
        )
    )
    if not matches:
        raise ValueError(
            f"Version {info['version']!r} contains no valid version numbers: see "
            f"https://packaging.python.org/en/latest/specifications/version-specifiers/"
        )
    match = matches[-1]
    version = match.group()

    # Treat anything else in the version string as part of the name.
    start, end = match.span()
    strip_chars = " .-_"
    before = info["version"][:start].strip(strip_chars)
    after = info["version"][end:].strip(strip_chars)
    name = " ".join(s for s in [name, before, after] if s)

    return name, version


# Some installer types use the reverse domain ID to detect when the product is already
# installed, so it should be both unique between different products, and stable between
# different versions of a product.
def get_bundle_app_name(info, name):
    # If reverse_domain_identifier is provided, use it as-is, but verify that the last
    # component is a valid Python package name, as Briefcase requires.
    if (rdi := info.get("reverse_domain_identifier")) is not None:
        if "." not in rdi:
            raise ValueError(f"reverse_domain_identifier {rdi!r} contains no dots")
        bundle, app_name = rdi.rsplit(".", 1)

        if not re.fullmatch(
            r"[A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9]", app_name, flags=re.IGNORECASE
        ):
            raise ValueError(
                f"reverse_domain_identifier {rdi!r} doesn't end with a valid package "
                f"name: see "
                f"https://packaging.python.org/en/latest/specifications/name-normalization/"
            )

    # If reverse_domain_identifier isn't provided, generate it from the name.
    else:
        bundle = DEFAULT_REVERSE_DOMAIN_ID
        app_name = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if not app_name:
            raise ValueError(f"Name {name!r} contains no alphanumeric characters")

    return bundle, app_name


# Create a Briefcase configuration file. Using a full TOML writer rather than a Jinja
# template allows us to avoid escaping strings everywhere.
def write_pyproject_toml(tmp_dir, info):
    name, version = get_name_version(info)
    bundle, app_name = get_bundle_app_name(info, name)

    config = {
        "project_name": name,
        "bundle": bundle,
        "version": version,
        "license": ({"file": info["license_file"]} if "license_file" in info else {"text": ""}),
        "app": {
            app_name: {
                "formal_name": f"{info['name']} {info['version']}",
                "description": "",  # Required, but not used in the installer.
                "external_package_path": EXTERNAL_PACKAGE_PATH,
                "external_package_executable_path": "",
                "use_full_install_path": False,
                "post_install_script": str(BRIEFCASE_DIR / "run_installation.bat"),
            }
        },
    }

    if "company" in info:
        config["author"] = info["company"]

    (tmp_dir / "pyproject.toml").write_text(tomli_w.dumps({"tool": {"briefcase": config}}))


def create(info, verbose=False):
    tmp_dir = Path(tempfile.mkdtemp())
    write_pyproject_toml(tmp_dir, info)

    external_dir = tmp_dir / EXTERNAL_PACKAGE_PATH
    external_dir.mkdir()
    preconda.write_files(info, external_dir)
    preconda.copy_extra_files(info.get("extra_files", []), external_dir)

    download_dir = Path(info["_download_dir"])
    pkgs_dir = external_dir / "pkgs"
    for dist in info["_dists"]:
        shutil.copy(download_dir / filename_dist(dist), pkgs_dir)

    copy_conda_exe(external_dir, "_conda.exe", info["_conda_exe"])

    briefcase = Path(sysconfig.get_path("scripts")) / "briefcase.exe"
    logger.info("Building installer")
    run(
        [briefcase, "package"] + (["-v"] if verbose else []),
        cwd=tmp_dir,
        check=True,
    )

    dist_dir = tmp_dir / "dist"
    msi_paths = list(dist_dir.glob("*.msi"))
    if len(msi_paths) != 1:
        raise RuntimeError(f"Found {len(msi_paths)} MSI files in {dist_dir}")
    shutil.copy(msi_paths[0], info["_outpath"])

    if not info.get("_debug"):
        shutil.rmtree(tmp_dir)
