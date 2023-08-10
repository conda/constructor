import itertools
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path
from shutil import which

import pytest

if sys.platform == "darwin":
    from constructor.osxpkg import OSX_DIR
from constructor.shar import read_header_template
from constructor.utils import preprocess


@lru_cache()
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


def test_linux_template_processing():
    template = read_header_template()
    errors = []
    for (
        osx,
        direct_execute_post_install,
        direct_execute_pre_install,
        batch_mode,
        keep_pkgs,
        has_conda,
        has_license,
        initialize_conda,
        initialize_by_default,
        has_post_install,
        has_pre_install,
        check_path_spaces,
        arch,
    ) in itertools.product(
        [False, True],
        [False, True],
        [False, True],
        [False, True],
        [False, True],
        [False, True],
        [False, True],
        [False, True],
        [False, True],
        [False, True],
        [False, True],
        [False, True],
        ["x86", "x86_64", " ppc64le", "s390x", "aarch64"],
    ):
        params = {
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
        }
        processed = preprocess(template, params)
        for template_string in ["#if", "#else", "#endif"]:
            if template_string in processed:
                errors.append(f"Found '{template_string}' after "
                              f"processing header.sh with '{params}'.")

    assert not errors


@pytest.mark.parametrize("arch", ["x86_64", "arm64"])
@pytest.mark.parametrize("check_path_spaces", [False, True])
@pytest.mark.parametrize("script", sorted(Path(OSX_DIR).glob("*.sh")))
def test_osxpkg_scripts_template_processing(arch, check_path_spaces, script):
    with script.open() as f:
        data = f.read()
    processed = preprocess(data, {"arch": arch, "check_path_spaces": check_path_spaces})
    assert "#if" not in processed
    assert "#else" not in processed
    assert "#endif" not in processed


@pytest.mark.skipif(available_command("shellcheck") is False, reason="requires shellcheck")
@pytest.mark.parametrize("arch", ["x86_64", "arm64"])
@pytest.mark.parametrize("check_path_spaces", [False, True])
@pytest.mark.parametrize("script", sorted(Path(OSX_DIR).glob("*.sh")))
def test_osxpkg_scripts_shellcheck(arch, check_path_spaces, script):
    with script.open() as f:
        data = f.read()
    processed = preprocess(data, {"arch": arch, "check_path_spaces": check_path_spaces})

    findings, returncode = run_shellcheck(processed)
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
):
    template = read_header_template()
    processed = preprocess(
        template,
        {
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
        },
    )

    findings, returncode = run_shellcheck(processed)
    assert findings == []
    assert returncode == 0
