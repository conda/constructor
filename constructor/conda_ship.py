"""Helpers for recording conda-ship runtime installations."""

from __future__ import annotations

import shlex
from pathlib import PurePosixPath, PureWindowsPath

from ._schema import InstallerTypes
from .utils import bat_env_var_esc, win_str_esc


def _single_line(name: str, value: str) -> str:
    if "\0" in value or "\n" in value or "\r" in value:
        raise ValueError(f"conda_ship_runtime.{name} must be a single line")
    return value


def _relative_path(name: str, value: str) -> str:
    _single_line(name, value)
    if PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute():
        raise ValueError(f"conda_ship_runtime.{name} must be relative to the constructor prefix")
    if ".." in PurePosixPath(value.replace("\\", "/")).parts:
        raise ValueError(f"conda_ship_runtime.{name} must not contain '..'")
    return value


def _relative_parts(value: str) -> tuple[str, ...]:
    return tuple(
        part.casefold() for part in PurePosixPath(value.replace("\\", "/")).parts if part != "."
    )


def validate_runtime_installation(info: dict, installer_types: tuple[InstallerTypes, ...]) -> None:
    """Validate the optional conda-ship runtime installation configuration."""
    runtime = info.get("conda_ship_runtime")
    if runtime is None:
        return

    if InstallerTypes.DOCKER in installer_types:
        raise ValueError("conda_ship_runtime is not supported for Docker outputs")

    executable = _relative_path("executable", runtime["executable"])
    managed_prefix = runtime.get("managed_prefix")
    if managed_prefix:
        _relative_path("managed_prefix", managed_prefix)
        executable_parts = _relative_parts(executable)
        managed_prefix_parts = _relative_parts(managed_prefix)
        if not managed_prefix_parts or executable_parts[: len(managed_prefix_parts)] == (
            managed_prefix_parts
        ):
            raise ValueError(
                "conda_ship_runtime.managed_prefix must not contain the runtime executable"
            )
    elif any(
        installer_type in installer_types
        for installer_type in (InstallerTypes.PKG, InstallerTypes.EXE, InstallerTypes.MSI)
    ):
        raise ValueError(
            "conda_ship_runtime.managed_prefix is required for PKG, EXE, and MSI outputs"
        )

    ownership = runtime.get("ownership", "direct")
    instruction = runtime.get("instruction")
    installation = _single_line("installation", runtime.get("installation", "constructor"))
    if (
        not installation
        or len(installation) > 64
        or not installation[0].isascii()
        or not (installation[0].islower() or installation[0].isdigit())
        or any(
            not byte.isascii() or not (byte.islower() or byte.isdigit() or byte == "-")
            for byte in installation[1:]
        )
    ):
        raise ValueError("conda_ship_runtime.installation must be a lowercase ASCII identifier")
    if instruction:
        _single_line("instruction", instruction)
    if instruction is not None and not instruction.strip():
        raise ValueError("conda_ship_runtime.instruction must not be empty")
    if ownership == "direct" and instruction is not None:
        raise ValueError(
            "conda_ship_runtime.instruction is only valid when ownership is 'external'"
        )
    if ownership == "external" and not instruction:
        raise ValueError("conda_ship_runtime.instruction is required when ownership is 'external'")

    windows_values = [
        runtime["executable"],
        runtime.get("managed_prefix"),
        runtime.get("installation", "constructor"),
        instruction,
    ]
    if InstallerTypes.EXE in installer_types and any(
        quote in value for value in windows_values if value is not None for quote in ("'", '"')
    ):
        raise ValueError(
            "conda_ship_runtime values must not contain single or double quotes for EXE outputs"
        )
    if InstallerTypes.MSI in installer_types and any(
        '"' in value for value in windows_values if value is not None
    ):
        raise ValueError("conda_ship_runtime values must not contain double quotes for MSI outputs")


def _runtime(info: dict) -> dict | None:
    runtime = info.get("conda_ship_runtime")
    if runtime is None:
        return None
    return {
        "executable": runtime["executable"],
        "managed_prefix": runtime.get("managed_prefix"),
        "ownership": runtime.get("ownership", "direct"),
        "installation": runtime.get("installation", "constructor"),
        "instruction": runtime.get("instruction"),
    }


def unix_runtime_installation(info: dict) -> dict | None:
    """Return shell-safe values for a Unix installer template."""
    runtime = _runtime(info)
    if runtime is None:
        return None

    return {
        key: shlex.quote(value.replace("\\", "/")) if value is not None else None
        for key, value in runtime.items()
    }


def batch_runtime_installation(info: dict) -> dict | None:
    """Return batch-safe values for the MSI installer template."""
    runtime = _runtime(info)
    if runtime is None:
        return None

    return {
        key: bat_env_var_esc(value.replace("/", "\\"))
        if key in {"executable", "managed_prefix"} and value is not None
        else bat_env_var_esc(value)
        if value is not None
        else None
        for key, value in runtime.items()
    }


def nsis_runtime_installation(info: dict) -> dict | None:
    """Return NSIS-safe values for the EXE installer template."""
    runtime = _runtime(info)
    if runtime is None:
        return None

    executable = runtime["executable"].replace("/", "\\")
    managed_prefix = runtime["managed_prefix"]
    if managed_prefix is not None:
        managed_prefix = managed_prefix.replace("/", "\\")

    return {
        "executable": win_str_esc(executable)[1:-1],
        "managed_prefix": (
            win_str_esc(managed_prefix)[1:-1] if managed_prefix is not None else None
        ),
        "ownership": win_str_esc(runtime["ownership"]),
        "installation": win_str_esc(runtime["installation"]),
        "instruction": (
            win_str_esc(runtime["instruction"]) if runtime["instruction"] is not None else None
        ),
    }
