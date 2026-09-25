"""Reusable types that are used in both the schema and constructor code.

This avoids requiring pydantic as a run dependency.
"""

try:
    from enum import StrEnum
except ImportError:  # Python < 3.11
    # Since StrEnums were added in Python 3.11, we need to have a temporary wrapper class
    # to handle Python 3.10 until we remove the support of it.
    from enum import Enum

    class StrEnum(str, Enum):
        def __str__(self):
            return str(self.value)


class InstallerTypes(StrEnum):
    # If you add a member that produces a single file named after itself (like
    # EXE/MSI/PKG/SH), also update FILE_INSTALLER_TYPES in tests/test_examples.py.
    ALL = "all"
    EXE = "exe"
    MSI = "msi"
    PKG = "pkg"
    SH = "sh"
    DOCKER = "docker"


class BuildOutputs(StrEnum):
    "Allowed keys in 'build_outputs' setting."

    HASH = "hash"
    INFO_JSON = "info.json"
    LICENSES = "licenses"
    LOCKFILE = "lockfile"
    PKGS_LIST = "pkgs_list"
