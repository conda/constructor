"""
Logic to build installers using Briefcase.
"""

import functools
import logging
import re
import shutil
import sys
import sysconfig
import tarfile
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
from .jinja import render_template
from .utils import (
    DEFAULT_REVERSE_DOMAIN_ID,
    bat_echo_esc,
    bat_env_var_esc,
    copy_conda_exe,
    filename_dist,
    get_final_channels,
    shortcuts_flags,
)

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


def _get_script_env_variables(info: dict) -> dict[str, str]:
    """Validate and escape script_env_variables for batch file use.

    Raises ValueError if any key or value contains double quotes.
    Returns escaped key-value pairs.
    """
    raw_vars = info.get("script_env_variables", {})
    escaped_vars = {}

    for key, val in raw_vars.items():
        if '"' in key or '"' in val:
            raise ValueError(
                f"script_env_variables entry '{key}' contains double quotes, "
                "which are not supported in MSI installers. "
                "Use single quotes instead."
            )
        escaped_vars[key] = bat_env_var_esc(val)

    return escaped_vars


def _setup_envs_commands(info: dict) -> list[dict]:
    """Build environment setup data for base and extra_envs.

    Returns a list of dicts, each containing the data needed to install
    one environment. Used by the run_installation.bat template.
    """
    environments = []

    # Base environment
    environments.append(
        {
            "name": "base",
            "prefix": "%BASE_PATH%",
            "lockfile": r"%BASE_PATH%\conda-meta\initial-state.explicit.txt",
            "channels": ",".join(get_final_channels(info)),
            "shortcuts": shortcuts_flags(info),
        }
    )

    # Extra environments
    for env_name in info.get("_extra_envs_info", {}):
        env_config = info["extra_envs"][env_name]
        # Needed for shortcuts_flags function
        if "_conda_exe_type" not in env_config:
            env_config["_conda_exe_type"] = info.get("_conda_exe_type")
        channel_info = {
            "channels": env_config.get("channels", info.get("channels", ())),
            "channels_remap": env_config.get("channels_remap", info.get("channels_remap", ())),
        }
        environments.append(
            {
                "name": env_name,
                "prefix": rf"%BASE_PATH%\envs\{env_name}",
                "lockfile": rf"%BASE_PATH%\envs\{env_name}\conda-meta\initial-state.explicit.txt",
                "channels": ",".join(get_final_channels(channel_info)),
                "shortcuts": shortcuts_flags(env_config),
            }
        )

    return environments


def create_uninstall_options_list(info: dict) -> list[dict]:
    """Returns a list of dicts with data formatted for the uninstallation options page."""
    return [
        {
            "name": "remove_user_data",
            "title": "Remove user data",
            "description": "Remove user data associated with this installation.",
            "default": False,
        },
        {
            "name": "remove_caches",
            "title": "Remove caches",
            "description": "Clear the package cache upon completion.",
            "default": False,
        },
        {
            "name": "remove_config_files",
            "title": "Remove configuration files",
            "description": "Remove .condarc and other configuration files.",
            "default": False,
        },
    ]


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
                "default": True,
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


def _get_python_info(info: dict) -> tuple[bool, list[str]]:
    """Return (has_python, pyver_components) by inspecting _dists."""
    for dist in info.get("_dists", []):
        name, version, _ = filename_dist(dist).rsplit("-", 2)
        if name == "python":
            return True, version.split(".")
    return False, []


@dataclass
class Payload:
    """
    This class manages and prepares a payload with a temporary directory.
    """

    info: dict
    archive_name: str = "payload.tar.gz"
    conda_exe_name: str = "_conda.exe"

    # Enable additional log output during pre/post uninstall/install.
    add_debug_logging: bool = False

    @functools.cached_property
    def root(self) -> Path:
        """Create root upon first access and cache it."""
        return Path(tempfile.mkdtemp(prefix="payload-"))

    def remove(self, *, ignore_errors: bool = True) -> None:
        """Remove the root of the payload.

        This function requires some extra care due to the root directory being a cached property.
        """
        root = getattr(self, "root", None)
        if root is None:
            return
        shutil.rmtree(root, ignore_errors=ignore_errors)
        # Now we drop the cached value so next access will recreate if desired
        try:
            delattr(self, "root")
        except Exception:
            # delattr on a cached_property may raise on some versions / edge cases
            pass

    def prepare(self) -> tuple:
        """Prepares the payload.

        Directory structure created during preparation:

            <root>/                          (temporary directory, see :attr:`root`)
            └── <EXTERNAL_PACKAGE_PATH>/     (external_dir: contains the payload archive and conda exe)
                └── base/                    (base_dir: represents the base conda environment)
                    └── pkgs/                (pkgs_dir: staging area for conda package distributions)
        """
        root = self.root
        external_dir = root / EXTERNAL_PACKAGE_PATH
        external_dir.mkdir(parents=True, exist_ok=True)

        # Note that the directory name "base" is also explicitly defined in `run_installation.bat`
        base_dir = external_dir / "base"
        base_dir.mkdir()

        pkgs_dir = base_dir / "pkgs"
        pkgs_dir.mkdir()
        # Render the template files and add them to the necessary config field
        self.render_templates()
        self.write_pyproject_toml(root, external_dir)

        preconda.write_files(self.info, base_dir)
        preconda.copy_extra_files(self.info.get("extra_files", []), external_dir)
        self._stage_dists(pkgs_dir)
        self._stage_conda(external_dir)

        archive_path = self.make_archive(base_dir, external_dir)
        if not archive_path.exists():
            raise RuntimeError(f"Unexpected error, failed to create archive: {archive_path}")
        return (root, external_dir, base_dir, pkgs_dir)

    def make_archive(self, src: Path, dst: Path) -> Path:
        """Create an archive of the directory 'src'.
        The input 'src' must be an existing directory.
        If 'dst' does not exist, this function will create it.
        The directory specified via 'src' is removed after successful creation.
        Returns the path to the archive.

        Example:
            payload = Payload(...)
            foo = Path('foo')
            bar = Path('bar')
            targz = payload.make_archive(foo, bar)
            This will create the file bar\\<payload.archive_name> containing 'foo' and all its contents.

        """
        if not src.is_dir():
            raise NotADirectoryError(src)
        dst.mkdir(parents=True, exist_ok=True)

        archive_path = dst / self.archive_name

        archive_type = archive_path.suffix[1:]  # since suffix starts with '.'
        with tarfile.open(archive_path, mode=f"w:{archive_type}", compresslevel=1) as tar:
            tar.add(src, arcname=src.name)

        shutil.rmtree(src)
        return archive_path

    def render_templates(self) -> list[Path]:
        """Render the configured templates under the payload root,
        returns a list of Paths to the rendered templates.
        """
        templates = {
            Path(BRIEFCASE_DIR / "run_installation.bat"): Path(self.root / "run_installation.bat"),
            Path(BRIEFCASE_DIR / "pre_uninstall.bat"): Path(self.root / "pre_uninstall.bat"),
        }

        has_python, pyver_components = _get_python_info(self.info)

        context: dict = {
            "archive_name": self.archive_name,
            "conda_exe_name": self.conda_exe_name,
            "add_debug": self.add_debug_logging,
            "register_envs": str(self.info.get("register_envs", True)).lower(),
            # --- has_python / pyver_components ---
            "has_python": has_python,
            "pyver_components": pyver_components,
            # --- OPTION_INITIALIZE_CONDA ---
            "initialize_conda": self.info.get("initialize_conda", "classic"),
            # --- OPTION_CLEAR_PACKAGE_CACHE / OPTION_ENABLE_SHORTCUTS ---
            "no_rcs_arg": self.info.get("_ignore_condarcs_arg", ""),
            # --- OPTION_ENABLE_SHORTCUTS ---
            # shortcuts_flags returns the appropriate --shortcuts-only=... flags,
            # an empty string (all shortcuts), or --no-shortcuts (none).
            # In the .bat template this is used in the "shortcuts enabled" branch,
            # so passing an empty string here is correct when all shortcuts are wanted.
            "shortcuts": shortcuts_flags(self.info),
            # --- setup_envs ---
            "setup_envs": _setup_envs_commands(self.info),
            # --- virtual_specs ---
            # virtual_specs: quoted for command-line use
            # virtual_specs_debug: unquoted for display
            # virtual_specs_debug_bat: escaped for batch echo commands
            "virtual_specs": " ".join([f'"{spec}"' for spec in self.info.get("virtual_specs", ())]),
            "virtual_specs_debug": " ".join(self.info.get("virtual_specs", ())),
            "virtual_specs_debug_bat": bat_echo_esc(" ".join(self.info.get("virtual_specs", ()))),
            # --- script_env_variables ---
            # User-defined environment variables for pre/post install scripts
            "script_env_variables": _get_script_env_variables(self.info),
        }

        # Render the templates now using jinja and the defined context
        for src, dst in templates.items():
            if not src.exists():
                raise FileNotFoundError(src)
            rendered = render_template(src.read_text(encoding="utf-8"), **context)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(rendered, encoding="utf-8", newline="\r\n")

        return list(templates.values())

    def write_pyproject_toml(self, root: Path, external: Path) -> None:
        name, version = get_name_version(self.info)
        bundle, app_name = get_bundle_app_name(self.info, name)

        config = {
            "project_name": name,
            "bundle": bundle,
            "version": version,
            "license": get_license(self.info),
            "app": {
                app_name: {
                    "formal_name": f"{self.info['name']} {self.info['version']}",
                    "description": "",  # Required, but not used in the installer.
                    "external_package_path": str(external),
                    "use_full_install_path": False,
                    "install_launcher": False,
                    "install_option": create_install_options_list(self.info),
                    "uninstall_option": create_uninstall_options_list(self.info),
                    "post_install_script": str(root / "run_installation.bat"),
                    "pre_uninstall_script": str(root / "pre_uninstall.bat"),
                }
            },
        }

        # Add optional content
        if "company" in self.info:
            config["author"] = self.info["company"]

        # Finalize
        (root / "pyproject.toml").write_text(tomli_w.dumps({"tool": {"briefcase": config}}))
        logger.debug(f"Created TOML file at: {root}")

    def _stage_dists(self, pkgs_dir: Path) -> None:
        download_dir = Path(self.info["_download_dir"])
        # Collect dists from base and extra_envs, de-duplicated
        dists = self.info["_dists"].copy()
        for env_info in self.info.get("_extra_envs_info", {}).values():
            dists += env_info["_dists"]
        for dist in sorted(set(dists)):
            shutil.copy(download_dir / filename_dist(dist), pkgs_dir)

    def _stage_conda(self, external_dir: Path) -> None:
        copy_conda_exe(external_dir, self.conda_exe_name, self.info["_conda_exe"])


def create(info, verbose=False):
    if not IS_WINDOWS:
        raise Exception(f"Invalid platform '{sys.platform}'. MSI installers require Windows.")

    if not info.get("_conda_exe_supports_logging"):
        raise Exception("MSI installers require conda-standalone with logging support.")

    # MSI installers always use conda-standalone for uninstallation.
    # This ensures proper cleanup of conda init, environments, and shortcuts
    # via the `conda constructor uninstall` command.
    info["uninstall_with_conda_exe"] = True

    payload = Payload(info)
    payload.prepare()

    briefcase = Path(sysconfig.get_path("scripts")) / "briefcase.exe"
    if not briefcase.exists():
        raise FileNotFoundError(
            f"Dependency 'briefcase' does not seem to be installed.\nTried: {briefcase}"
        )

    logger.info("Building MSI installer")
    run(
        [briefcase, "package"] + (["-v"] if verbose else []),
        cwd=payload.root,
        check=True,
    )

    dist_dir = payload.root / "dist"
    msi_paths = list(dist_dir.glob("*.msi"))
    if len(msi_paths) != 1:
        raise RuntimeError(f"Found {len(msi_paths)} MSI files in {dist_dir}, expected 1.")

    outpath = Path(info["_outpath"])
    outpath.unlink(missing_ok=True)
    shutil.move(msi_paths[0], outpath)

    if not info.get("_debug"):
        payload.remove()
