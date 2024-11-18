import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path
from shutil import which

import pytest

if sys.platform == "darwin":
    from constructor.osxpkg import OSX_DIR
else:
    # Tests with OSX_DIR are skipped, but a placeholder is needed for pytest
    OSX_DIR = ""
from constructor import __version__
from constructor.jinja import render_template
from constructor.shar import read_header_template


@lru_cache
def available_command(cmd):
    return which(cmd) is not None


def run_shellcheck(script):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sh") as f:
        f.write(script)
        f.flush()

        cmd = [
            "shellcheck",
            # https://www.shellcheck.net/wiki/SC2034
            "--exclude=SC2034",
            f"{f.name}",
        ]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        sc_stdout, _ = p.communicate()
        findings = sc_stdout.splitlines()
    return findings, p.returncode


@pytest.mark.skipif(sys.platform != "darwin", reason="Only on MacOS")
@pytest.mark.skipif(available_command("shellcheck") is False, reason="requires shellcheck")
@pytest.mark.parametrize("arch", ["x86_64", "arm64"])
@pytest.mark.parametrize("check_path_spaces", [False, True])
@pytest.mark.parametrize(
    "script", [pytest.param(path, id=str(path)) for path in sorted(Path(OSX_DIR).glob("*.sh"))]
)
def test_osxpkg_scripts_shellcheck(arch, check_path_spaces, script):
    with script.open() as f:
        data = f.read()
    processed = render_template(
        data,
        arch=arch,
        check_path_spaces=check_path_spaces,
        pkg_name_lower="example",
        installer_name="Example",
        installer_version="1.2.3",
        installer_platform="osx-64",
        channels="conda-forge",
        write_condarc="",
        path_exists_error_text="Error",
        progress_notifications=True,
        pre_or_post="pre",
        constructor_version=__version__,
        shortcuts="",
        enable_shortcuts=True,
        register_envs=True,
        virtual_specs="__osx>=10.13",
        no_rcs_arg="",
        script_env_variables="",
    )

    findings, returncode = run_shellcheck(processed)
    print(*findings, sep="\n")
    assert findings == []
    assert returncode == 0


@pytest.mark.skipif(available_command("shellcheck") is False, reason="requires shellcheck")
@pytest.mark.parametrize("osx", [False, True])
@pytest.mark.parametrize("direct_execute_post_install", [True])
@pytest.mark.parametrize("direct_execute_pre_install", [True])
@pytest.mark.parametrize("batch_mode", [True])
@pytest.mark.parametrize("keep_pkgs", [True])
@pytest.mark.parametrize("has_conda", [False, True])
@pytest.mark.parametrize("has_license", [True])
@pytest.mark.parametrize("initialize_conda", [True])
@pytest.mark.parametrize("initialize_by_default", [True])
@pytest.mark.parametrize("has_post_install", [True])
@pytest.mark.parametrize("has_pre_install", [False])
@pytest.mark.parametrize("arch", ["x86_64", "aarch64"])
@pytest.mark.parametrize("check_path_spaces", [True])
@pytest.mark.parametrize("enable_shortcuts", ["true"])
@pytest.mark.parametrize("min_glibc_version", ["2.17"])
@pytest.mark.parametrize("min_osx_version", ["10.13"])
def test_template_shellcheck(
    osx,
    arch,
    has_pre_install,
    has_post_install,
    initialize_conda,
    initialize_by_default,
    has_license,
    has_conda,
    keep_pkgs,
    batch_mode,
    direct_execute_pre_install,
    direct_execute_post_install,
    check_path_spaces,
    enable_shortcuts,
    min_glibc_version,
    min_osx_version,
):
    template = read_header_template()
    processed = render_template(
        template,
        **{
            "has_license": has_license,
            "osx": osx,
            "batch_mode": batch_mode,
            "keep_pkgs": keep_pkgs,
            "has_conda": has_conda,
            "x86": arch == "x86",
            "x86_64": arch == "x86_64",
            "ppc64le": arch == "ppc64le",
            "s390x": arch == "s390x",
            "aarch64": arch == "aarch64",
            "linux": not osx,
            "has_pre_install": has_pre_install,
            "direct_execute_pre_install": direct_execute_pre_install,
            "has_post_install": has_post_install,
            "direct_execute_post_install": direct_execute_post_install,
            "initialize_conda": initialize_conda,
            "initialize_by_default": initialize_by_default,
            "check_path_spaces": check_path_spaces,
            "enable_shortcuts": enable_shortcuts,
            "min_glibc_version": min_glibc_version,
            "min_osx_version": min_osx_version,
            "first_payload_size": "1024",
            "second_payload_size": "512",
            "constructor_version": __version__,
            "installer_name": "Example",
            "installer_version": "1.2.3",
            "installer_platform": "linux-64",
            "installer_md5": "a0098a2c837f4cf50180cfc0a041b2af",
            "script_env_variables": "",  # TODO: Fill this in with actual value
            "default_prefix": "/opt/Example",
            "license": "Some text",
            "total_installation_size_kb": "1024",
            "virtual_specs": "__glibc>=2.17",
            "shortcuts": "",
            "register_envs": "1",
            "channels": "conda-forge",
            "no_rcs_arg": "",
            "install_commands": "",  # TODO: Fill this in with actual value
            "conclusion_text": "Something",
        },
    )

    findings, returncode = run_shellcheck(processed)
    print(*findings, sep="\n")
    assert findings == []
    assert returncode == 0
