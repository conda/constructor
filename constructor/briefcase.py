"""
Logic to build installers using Briefcase.
"""

from __future__ import annotations

import logging
import re
import shutil
import sys
import sysconfig
import tempfile
from functools import cached_property
from pathlib import Path
from subprocess import run

import tomli_w

from . import preconda
from .utils import DEFAULT_REVERSE_DOMAIN_ID, copy_conda_exe, filename_dist

BRIEFCASE_DIR = Path(__file__).parent / "briefcase"
EXTERNAL_PACKAGE_PATH = "external"

logger = logging.getLogger(__name__)


def get_name_version(info):
    if not (name := info.get("name")):
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


def get_license(info):
    """Retrieve the specified license as a dict or return a placeholder if not set."""

    if "license_file" in info:
        return {"file": info["license_file"]}
    # We cannot return an empty string because that results in an exception on the briefcase side.
    return {"text": "TODO"}


class UninstallBat:
    """Represents a pre-uninstall batch script handler for the MSI installers.
    This is intended to handle both the user specified 'pre_uninstall' bat script
    and also the 'pre_uninstall_script' passed to briefcase by merging them into one.
    """

    def __init__(self, dst: Path, user_script: str | None):
        """
        Parameters
        ----------
        dst : Path
            Destination directory where the generated `pre_uninstall.bat` file
            will be written.
        user_script : str | None
            Optional path (string) to a user-provided `.bat` file configured
            via the `pre_uninstall` setting in the installer configuration.
            If provided, the file must adhere to the schema.
        """
        self._dst = dst

        self.user_script = None
        if user_script:
            user_script_path = Path(user_script)
            if not self.is_bat_file(user_script_path):
                raise ValueError(
                    f"The entry '{user_script}' configured via 'pre_uninstall' "
                    "must be a path to an existing .bat file."
                )
            self.user_script = user_script_path
        self._encoding = "utf-8"  # TODO: Do we want to use utf-8-sig?

    def is_bat_file(self, file_path: Path) -> bool:
        return file_path.is_file() and file_path.suffix.lower() == ".bat"

    def user_script_as_list(self) -> list[str]:
        """Read user script."""
        if not self.user_script:
            return []
        with open(self.user_script, encoding=self._encoding, newline=None) as f:
            return f.read().splitlines()

    def sanitize_input(self, input_list: list[str]) -> list[str]:
        """Sanitizes the input, adds a safe exit if necessary.
        Assumes the contents of the input represents the contents of a .bat-file.
        """
        return ["exit /b" if line.strip().lower() == "exit" else line for line in input_list]

    def create(self) -> None:
        """Create the bat script for uninstallation. The script will also include the contents from the file the user
        may have specified in the yaml-file via 'pre_uninstall'.
        When this function is called, the directory 'dst' specified at class instantiation must exist.
        """
        if not self._dst.exists():
            raise FileNotFoundError(
                f"The directory {self._dst} must exist in order to create the file."
            )

        header = [
            "@echo off",
            "setlocal enableextensions enabledelayedexpansion",
            'set "_HERE=%~dp0"',
            "",
            "rem === Pre-uninstall script ===",
        ]

        user_bat: list[str] = []

        if self.user_script:
            # user_script: list = self.sanitize(self.user_script_as_list())
            # TODO: Embed user script and run it as a subroutine.
            #       Add error handling using unique labels with 'goto'
            user_bat += [
                "rem User supplied a script",
            ]

        """
         The goal is to remove most of the files except for the directory '_installer' where
         the bat-files are located. This is because the MSI Installer needs to call these bat-files
         after 'pre_uninstall_script' is finished, in order to finish with the uninstallation.
        """
        main_bat = [
            'echo "Preparing uninstallation..."',
            r'set "INSTDIR=%_HERE%\.."',
            'set "CONDA_EXE=_conda.exe"',
            r'"%INSTDIR%\%CONDA_EXE%" menuinst --prefix "%INSTDIR%" --remove',
            r'"%INSTDIR%\%CONDA_EXE%" remove -p "%INSTDIR%" --keep-env --all -y',
            "if errorlevel 1 (",
            "    echo [ERROR] %CONDA_EXE% failed with exit code %errorlevel%.",
            "    exit /b %errorlevel%",
            ")",
            "",
            "echo [INFO] %CONDA_EXE% completed successfully.",
            r'set "PKGS=%INSTDIR%\pkgs"',
            'if exist "%PKGS%" (',
            '    echo [INFO] Removing "%PKGS%" ...',
            '    rmdir /s /q "%PKGS%"',
            "    echo [INFO] Done.",
            ")",
            "",
            r'set "NONADMIN=%INSTDIR%\.nonadmin"',
            'if exist "%NONADMIN%" (',
            '    echo [INFO] Removing file "%NONADMIN%" ...',
            '    del /f /q "%NONADMIN%"',
            ")",
            "",
        ]
        final_lines = header + [""] + user_bat + [""] + main_bat

        with open(self.file_path, "w", encoding=self._encoding, newline="\r\n") as f:
            # Python will write \n as \r\n since we have set the 'newline' argument above.
            f.writelines(line + "\n" for line in final_lines)

    @cached_property
    def file_path(self) -> Path:
        """The absolute path to the generated `pre_uninstall.bat` file."""
        return self._dst / "pre_uninstall.bat"


# Create a Briefcase configuration file. Using a full TOML writer rather than a Jinja
# template allows us to avoid escaping strings everywhere.
def write_pyproject_toml(tmp_dir, info, uninstall_bat):
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
                "pre_uninstall_script": str(uninstall_bat.file_path),
            }
        },
    }

    if "company" in info:
        config["author"] = info["company"]

    (tmp_dir / "pyproject.toml").write_text(tomli_w.dumps({"tool": {"briefcase": config}}))


def create(info, verbose=False):
    if sys.platform != "win32":
        raise Exception(f"Invalid platform '{sys.platform}'. Only Windows is supported.")

    tmp_dir = Path(tempfile.mkdtemp())

    uninstall_bat = UninstallBat(tmp_dir, info.get("pre_uninstall", None))
    uninstall_bat.create()

    write_pyproject_toml(tmp_dir, info, uninstall_bat)

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
    if not briefcase.exists():
        raise FileNotFoundError(
            f"Dependency 'briefcase' does not seem to be installed.\nTried: {briefcase}"
        )
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

    outpath = Path(info["_outpath"])
    outpath.unlink(missing_ok=True)
    shutil.move(msi_paths[0], outpath)

    if not info.get("_debug"):
        shutil.rmtree(tmp_dir)
