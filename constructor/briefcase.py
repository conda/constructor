"""
Logic to build installers using Briefcase.
"""

import logging
import re
import shutil
import sys
import sysconfig
import tempfile
from dataclasses import dataclass
from pathlib import Path
from subprocess import run

IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    import tomli_w
else:
    tomli_w = None  # This file is only intended for Windows use

from . import preconda
from .utils import DEFAULT_REVERSE_DOMAIN_ID, copy_conda_exe, filename_dist

BRIEFCASE_DIR = Path(__file__).parent / "briefcase"
EXTERNAL_PACKAGE_PATH = "external"

# Default to a low version, so that if a valid version is provided in the future, it'll
# be treated as an upgrade.
DEFAULT_VERSION = "0.0.1"

logger = logging.getLogger(__name__)


def get_name_version(info):
    if not (name := info.get("name")):
        raise ValueError("Name is empty")
    if not (version := info.get("version")):
        raise ValueError("Version is empty")

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
            version.lower().replace("-", "."),
        )
    )
    if not matches:
        logger.warning(
            f"Version {version!r} contains no valid version numbers; "
            f"defaulting to {DEFAULT_VERSION}"
        )
        return f"{name} {version}", DEFAULT_VERSION

    match = matches[-1]
    version = match.group()

    # Treat anything else in the version string as part of the name.
    start, end = match.span()
    strip_chars = " .-_"
    before = info["version"][:start].strip(strip_chars)
    after = info["version"][end:].strip(strip_chars)
    name = " ".join(s for s in [name, before, after] if s)

    return name, version


# Takes an arbitrary string with at least one alphanumeric character, and makes it into
# a valid Python package name.
def make_app_name(name, source):
    app_name = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not app_name:
        raise ValueError(f"{source} contains no alphanumeric characters")
    return app_name


# Some installer types use the reverse domain ID to detect when the product is already
# installed, so it should be both unique between different products, and stable between
# different versions of a product.
def get_bundle_app_name(info, name):
    # If reverse_domain_identifier is provided, use it as-is,
    if (rdi := info.get("reverse_domain_identifier")) is not None:
        if "." not in rdi:
            raise ValueError(f"reverse_domain_identifier {rdi!r} contains no dots")
        bundle, app_name = rdi.rsplit(".", 1)

        # Ensure that the last component is a valid Python package name, as Briefcase
        # requires.
        if not re.fullmatch(
            r"[A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9]", app_name, flags=re.IGNORECASE
        ):
            app_name = make_app_name(
                app_name, f"Last component of reverse_domain_identifier {rdi!r}"
            )

    # If reverse_domain_identifier isn't provided, generate it from the name.
    else:
        bundle = DEFAULT_REVERSE_DOMAIN_ID
        app_name = make_app_name(name, f"Name {name!r}")

    return bundle, app_name


def get_license(info):
    """Retrieve the specified license as a dict or return a placeholder if not set."""

    if "license_file" in info:
        return {"file": info["license_file"]}

    placeholder_license = Path(__file__).parent / "nsis" / "placeholder_license.txt"
    return {"file": str(placeholder_license)}  # convert to str for TOML serialization


def is_bat_file(file_path: Path) -> bool:
    return file_path.is_file() and file_path.suffix.lower() == ".bat"


def create_install_options_list(info: dict) -> list[dict]:
    """Returns a list of dicts with data formatted for the installation options page."""
    options = []

    # Register Python (if Python is bundled)
    has_python = False
    for item in info.get("_dists", []):
        if item.startswith("python-"):
            components = item.split("-")  # python-x.y.z-<build number>.suffix
            python_version = ".".join(components[1].split(".")[:-1])  # create the string "x.y"
            has_python = True
            break

    if has_python and info.get("register_python", True):
        options.append(
            {
                "name": "register_python",
                "title": f"Register {info['name']} as my default Python {python_version}.",
                "description": "Allows other programs, such as VSCode, PyCharm, etc. to automatically "
                f"detect {info['name']} as the primary Python {python_version} on the system.",
                "default": info.get("register_python_default", False),
            }
        )

    # Initialize conda
    initialize_conda = info.get("initialize_conda", "classic")
    if initialize_conda:
        if initialize_conda == "condabin":
            description = (
                "Adds condabin, which only contains the 'conda' executables, to PATH. "
                "Does not require special shortcuts but activation needs "
                "to be performed manually."
            )
        else:
            description = (
                "NOT recommended. This can lead to conflicts with other applications. "
                "Instead, use the Command Prompt and Powershell menus added to the Windows Start Menu."
            )
        options.append(
            {
                "name": "initialize_conda",
                "title": "Add installation to my PATH environment variable",
                "description": description,
                "default": info.get("initialize_by_default", False),
            }
        )

    # Keep package option (presented to the user as a negation (clear package cache))
    clear_package_cache = not info.get("keep_pkgs", False)
    options.append(
        {
            "name": "clear_package_cache",
            "title": "Clear the package cache upon completion",
            "description": "Recommended. Recovers some disk space without harming functionality.",
            "default": clear_package_cache,
        }
    )

    # Enable shortcuts
    if info.get("_enable_shortcuts", False) is True:
        options.append(
            {
                "name": "enable_shortcuts",
                "title": "Create shortcuts",
                "description": "Create shortcuts (supported packages only).",
                "default": False,
            }
        )

    # Pre/Post install script
    for script_type in ["pre", "post"]:
        script_description = info.get(f"{script_type}_install_desc", "")
        script = info.get(f"{script_type}_install", "")
        if script_description and not script:
            raise ValueError(
                f"{script_type}_install_desc was set, but {script_type}_install was not!"
            )

        if script:
            script_path = Path(script)
            if not is_bat_file(script_path):
                raise ValueError(
                    f"Specified {script_type}-install script '{script}' must be an existing '.bat' file."
                )

        # The UI option is only displayed if a description is set
        if script_description:
            options.append(
                {
                    "name": f"{script_type}_install_script",
                    "title": f"{script_type.capitalize()}-install script",
                    "description": script_description,
                    "default": False,
                }
            )

    return options


# Create a Briefcase configuration file. Using a full TOML writer rather than a Jinja
# template allows us to avoid escaping strings everywhere.
def write_pyproject_toml(tmp_dir, info):
    name, version = get_name_version(info)
    bundle, app_name = get_bundle_app_name(info, name)

    config = {
        "project_name": name,
        "bundle": bundle,
        "version": version,
        "license": get_license(info),
        "app": {
            app_name: {
                "formal_name": f"{info['name']} {info['version']}",
                "description": "",  # Required, but not used in the installer.
                "external_package_path": EXTERNAL_PACKAGE_PATH,
                "use_full_install_path": False,
                "install_launcher": False,
                "post_install_script": str(BRIEFCASE_DIR / "run_installation.bat"),
                "install_option": create_install_options_list(info),
            }
        },
    }

    if "company" in info:
        config["author"] = info["company"]

    (tmp_dir / "pyproject.toml").write_text(tomli_w.dumps({"tool": {"briefcase": config}}))
    logger.debug(f"Created TOML file at: {tmp_dir}")


@dataclass(frozen=True)
class PayloadLayout:
    """A data class with purpose to contain the payload layout."""

    root: Path
    external: Path
    base: Path
    pkgs: Path


@dataclass
class Payload:
    """
    This class manages and prepares a payload with a temporary directory.
    """

    info: dict
    root: Path | None = None

    def prepare(self) -> PayloadLayout:
        root = self._ensure_root()
        self._write_pyproject(root)
        layout = self._create_layout(root)

        preconda.write_files(self.info, layout.base)
        preconda.copy_extra_files(self.info.get("extra_files", []), layout.external)
        self._stage_dists(layout)
        self._stage_conda(layout)
        return layout

    def remove(self) -> None:
        shutil.rmtree(self.root)

    def _write_pyproject(self, root: Path) -> None:
        write_pyproject_toml(root, self.info)

    def _ensure_root(self) -> Path:
        if self.root is None:
            self.root = Path(tempfile.mkdtemp())
        return self.root

    def _create_layout(self, root: Path) -> PayloadLayout:
        """The layout is created as:
        root/
        └── external/
            └── base/
                └── pkgs/
        """
        external_dir = root / EXTERNAL_PACKAGE_PATH
        external_dir.mkdir(parents=True, exist_ok=True)

        # Note that the directory name "base" is also explicitly defined in `run_installation.bat`
        base_dir = external_dir / "base"
        base_dir.mkdir()

        pkgs_dir = base_dir / "pkgs"
        pkgs_dir.mkdir()
        return PayloadLayout(root=root, external=external_dir, base=base_dir, pkgs=pkgs_dir)

    def _stage_dists(self, layout: PayloadLayout) -> None:
        download_dir = Path(self.info["_download_dir"])
        for dist in self.info["_dists"]:
            shutil.copy(download_dir / filename_dist(dist), layout.pkgs)

    def _stage_conda(self, layout: PayloadLayout) -> None:
        copy_conda_exe(layout.external, "_conda.exe", self.info["_conda_exe"])


def create(info, verbose=False):
    if not IS_WINDOWS:
        raise Exception(f"Invalid platform '{sys.platform}'. MSI installers require Windows.")

    payload = Payload(info)
    prepared_payload = payload.prepare()

    briefcase = Path(sysconfig.get_path("scripts")) / "briefcase.exe"
    if not briefcase.exists():
        raise FileNotFoundError(
            f"Dependency 'briefcase' does not seem to be installed.\nTried: {briefcase}"
        )

    logger.info("Building MSI installer")
    run(
        [briefcase, "package"] + (["-v"] if verbose else []),
        cwd=prepared_payload.root,
        check=True,
    )

    dist_dir = prepared_payload.root / "dist"
    msi_paths = list(dist_dir.glob("*.msi"))
    if len(msi_paths) != 1:
        raise RuntimeError(f"Found {len(msi_paths)} MSI files in {dist_dir}, expected 1.")

    outpath = Path(info["_outpath"])
    outpath.unlink(missing_ok=True)
    shutil.move(msi_paths[0], outpath)

    if not info.get("_debug"):
        payload.remove()
