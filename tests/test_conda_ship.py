from __future__ import annotations

import pytest

from constructor._schema import InstallerTypes
from constructor.conda_ship import (
    batch_runtime_installation,
    nsis_runtime_installation,
    unix_runtime_installation,
    validate_runtime_installation,
)


def runtime_info(**overrides):
    runtime = {
        "executable": "conda",
        "ownership": "direct",
        "installation": "constructor",
    }
    runtime.update(overrides)
    return {"conda_ship_runtime": runtime}


@pytest.mark.parametrize(
    "path",
    (
        "/usr/local/bin/conda",
        "../conda",
        "bin/../../conda",
        r"C:\Program Files\conda.exe",
        r"\\server\share\conda.exe",
    ),
)
def test_runtime_executable_must_be_relative(path):
    with pytest.raises(ValueError, match="conda_ship_runtime.executable"):
        validate_runtime_installation(
            runtime_info(executable=path),
            (InstallerTypes.SH,),
        )


def test_external_runtime_requires_instruction():
    with pytest.raises(ValueError, match="instruction is required"):
        validate_runtime_installation(
            runtime_info(ownership="external"),
            (InstallerTypes.SH,),
        )


def test_direct_runtime_rejects_instruction():
    with pytest.raises(ValueError, match="only valid when ownership is 'external'"):
        validate_runtime_installation(
            runtime_info(instruction="Run vendor update"),
            (InstallerTypes.SH,),
        )


@pytest.mark.parametrize("installation", ("", "Constructor", "constructor_plugin", "é"))
def test_installation_must_match_runtime_contract(installation):
    with pytest.raises(ValueError, match="lowercase ASCII identifier"):
        validate_runtime_installation(
            runtime_info(installation=installation),
            (InstallerTypes.SH,),
        )


@pytest.mark.parametrize(
    "installer_type",
    (InstallerTypes.PKG, InstallerTypes.EXE, InstallerTypes.MSI),
)
def test_elevated_installer_requires_managed_prefix(installer_type):
    with pytest.raises(ValueError, match="managed_prefix is required"):
        validate_runtime_installation(runtime_info(), (installer_type,))


@pytest.mark.parametrize(
    ("executable", "managed_prefix"),
    (
        ("conda", "."),
        ("runtime/conda", "runtime"),
        (r"runtime\conda.exe", "runtime"),
    ),
)
def test_managed_prefix_must_not_contain_runtime_executable(
    executable,
    managed_prefix,
):
    with pytest.raises(ValueError, match="must not contain the runtime executable"):
        validate_runtime_installation(
            runtime_info(executable=executable, managed_prefix=managed_prefix),
            (InstallerTypes.SH,),
        )


def test_docker_output_is_not_supported():
    with pytest.raises(ValueError, match="not supported for Docker"):
        validate_runtime_installation(
            runtime_info(managed_prefix="."),
            (InstallerTypes.SH, InstallerTypes.DOCKER),
        )


@pytest.mark.parametrize(
    "instruction",
    (
        "Run vendor's updater",
        'Run "vendor" updater',
    ),
)
def test_exe_values_reject_quotes(instruction):
    with pytest.raises(ValueError, match="single or double quotes"):
        validate_runtime_installation(
            runtime_info(
                managed_prefix="runtime",
                ownership="external",
                instruction=instruction,
            ),
            (InstallerTypes.EXE,),
        )


def test_msi_values_allow_single_quotes():
    validate_runtime_installation(
        runtime_info(
            managed_prefix="runtime",
            ownership="external",
            instruction="Run vendor's updater",
        ),
        (InstallerTypes.MSI,),
    )


def test_runtime_template_values():
    info = runtime_info(
        executable="bin/conda runtime",
        managed_prefix="managed prefix",
        ownership="external",
        installation="vendor-installer",
        instruction="Run vendor update",
    )
    validate_runtime_installation(info, (InstallerTypes.SH,))

    assert unix_runtime_installation(info) == {
        "executable": "'bin/conda runtime'",
        "managed_prefix": "'managed prefix'",
        "ownership": "external",
        "installation": "vendor-installer",
        "instruction": "'Run vendor update'",
    }
    assert batch_runtime_installation(info) == {
        "executable": r"bin\conda runtime",
        "managed_prefix": "managed prefix",
        "ownership": "external",
        "installation": "vendor-installer",
        "instruction": "Run vendor update",
    }
    assert nsis_runtime_installation(info) == {
        "executable": r"bin\conda runtime",
        "managed_prefix": "managed prefix",
        "ownership": '"external"',
        "installation": '"vendor-installer"',
        "instruction": '"Run vendor update"',
    }
