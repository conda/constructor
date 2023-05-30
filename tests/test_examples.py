import os
import shutil
import subprocess
import sys
import time
import warnings
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional, Tuple

import pytest

from constructor.osxpkg import calculate_install_dir

try:
    import coverage  # noqa

    COV_CMD = ("coverage", "run", "--branch", "--append", "-m")
except ImportError:
    COV_CMD = ()


pytestmark = pytest.mark.examples
REPO_DIR = Path(__file__).parent.parent
ON_CI = os.environ.get("CI")
CONSTRUCTOR_CONDA_EXE = os.environ.get("CONSTRUCTOR_CONDA_EXE")
CONSTRUCTOR_DEBUG = bool(os.environ.get("CONSTRUCTOR_DEBUG"))
if artifacts_path := os.environ.get("CONSTRUCTOR_EXAMPLES_KEEP_ARTIFACTS"):
    KEEP_ARTIFACTS_PATH = Path(artifacts_path)
    KEEP_ARTIFACTS_PATH.mkdir(parents=True, exist_ok=True)
else:
    KEEP_ARTIFACTS_PATH = None


def _execute(
    cmd: Iterable[str], installer_input=None, check=True, **env_vars
) -> subprocess.CompletedProcess:
    t0 = time.time()
    if env_vars:
        env = os.environ.copy()
        env.update({k: v for (k, v) in env_vars.items() if v is not None})
    else:
        env = None
    p = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE if installer_input else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    stdout, stderr = None, None
    try:
        stdout, stderr = p.communicate(input=installer_input, timeout=420)
        retcode = p.poll()
        if check and retcode:
            raise subprocess.CalledProcessError(retcode, cmd, output=stdout, stderr=stderr)
        return subprocess.CompletedProcess(cmd, retcode, stdout, stderr)
    except subprocess.TimeoutExpired:
        p.kill()
        stdout, stderr = p.communicate()
        raise
    finally:
        if stdout:
            print(stdout)
        if stderr:
            print(stderr, file=sys.stderr)
        print("Took", timedelta(seconds=time.time() - t0))


def _run_installer_exe(installer, install_dir, installer_input=None):
    """
    NSIS manual:
    > /D sets the default installation directory ($INSTDIR), overriding InstallDir
    > and InstallDirRegKey. It must be the last parameter used in the command line
    > and must not contain any quotes, even if the path contains spaces. Only
    > absolute paths are supported.
    Since subprocess.Popen WILL escape the spaces with quotes, we need to provide
    them as separate arguments. We don't care about multiple spaces collapsing into
    one, since the point is to just have spaces in the installation path -- one
    would be enough too :)
    This is why we have this weird .split() thingy down there in `/D=...`.
    """
    if not sys.platform.startswith("win"):
        raise ValueError("Can only run .exe installers on Windows")
    if "NSIS_USING_LOG_BUILD" not in os.environ:
        warnings.warn(
            "Windows installers are tested with NSIS in silent mode, which does "
            "not report errors on exit. You should use logging-enabled NSIS builds "
            "to generate an 'install.log' file this script will search for errors "
            "after completion."
        )
    cmd = ["cmd.exe", "/c", "start", "/wait", installer, "/S", *f"/D={install_dir}".split()]
    _execute(cmd)

    # Windows installers won't raise exit codes so we need to check the log file
    error_lines = []
    try:
        log_is_empty = True
        with open(os.path.join(install_dir, "install.log"), encoding="utf-16-le") as f:
            for line in f:
                log_is_empty = False
                if ":error:" in line:
                    error_lines.append(line)
        if log_is_empty:
            error_lines.append("Logfile was unexpectedly empty!")
    except Exception as exc:
        error_lines.append(
            f"Could not read logs! {exc.__class__.__name__}: {exc}\n"
            "This usually means that the destination folder could not be created.\n"
            "Possible causes: permissions, non-supported characters, long paths...\n"
            "Consider setting 'check_path_spaces' and 'check_path_length' to 'False'."
        )
    if error_lines:
        raise AssertionError("\n".join(error_lines))


def _run_uninstaller_exe(install_dir):
    # Now test the uninstallers
    if " " in str(install_dir):
        # TODO: We can't seem to run the uninstaller when there are spaces in the PATH
        return

    uninstaller = next(install_dir.glob("Uninstall-*.exe"), None)
    if not uninstaller:
        raise AssertionError("Could not find uninstaller!")
    cmd = [
        "cmd.exe",
        "/c",
        "start",
        "/wait",
        str(uninstaller),
        # We need silent mode + "uninstaller location" (_?=...) so the command can
        # be waited; otherwise, since the uninstaller copies itself to a different
        # location so it can be auto-deleted, it returns immediately and it gives
        # us problems with the tempdir cleanup later
        f"/S _?={install_dir}",
    ]
    _execute(cmd)
    remaining_files = list(install_dir.iterdir())
    if len(remaining_files) > 2:
        # The debug installer writes to install.log too, which will only
        # be deleted _after_ a reboot. Finding some files is ok, but more
        # than two usually means a problem with the uninstaller.
        # Note this is is not exhaustive, because we are not checking
        # whether the registry was restored, menu items were deleted, etc.
        # TODO :)
        raise AssertionError(f"Uninstaller left too many files: {remaining_files}")


def _run_installer_sh(installer, install_dir, installer_input=None):
    if installer_input:
        cmd = ["/bin/sh", installer]
    else:
        cmd = ["/bin/sh", installer, "-b", "-p", install_dir]
    return _execute(cmd, installer_input=installer_input)


def _run_installer_pkg(installer, install_dir, example_path=None):
    if os.environ.get("CI"):
        # We want to run it in an arbitrary directory, but the options
        # are limited here... We can only install to $HOME :shrug:
        # but that will pollute ~, so we only do it if we are running on CI
        cmd = [
            "installer",
            "-pkg",
            installer,
            "-dumplog",
            "-target",
            "CurrentUserHomeDirectory",
        ]
        if example_path:
            install_dir = calculate_install_dir(example_path / "construct.yaml")
            install_dir = Path(os.environ["HOME"]) / install_dir
    else:
        # This command only expands the PKG, but does not install
        warnings.warn(
            "Not running installer, only expanding the PKG. "
            "Export CI=1 to run it, but it will pollute your $HOME."
        )
        cmd = ["pkgutil", "--expand", installer, install_dir]
    return _execute(cmd), install_dir


def _sentinel_file_checks(example_path, install_dir):
    script_ext = "bat" if sys.platform.startswith("win") else "sh"
    for script_prefix in "pre", "post", "test":
        script = f"{script_prefix}_install.{script_ext}"
        sentinel = f"{script_prefix}_install_sentinel.txt"
        if (example_path / script).exists() and not (install_dir / sentinel).exists():
            raise AssertionError(
                f"Sentinel file for {script_prefix}_install not found! "
                f"{install_dir} contents:\n" + "\n".join(sorted(install_dir.iterdir()))
            )


def _run_installer(
    example_path: Path,
    installer: Path,
    install_dir: Path,
    installer_input: Optional[str] = None,
    check_sentinels=True,
    request=None,
):
    if installer.suffix == ".exe":
        _run_installer_exe(installer, install_dir, installer_input=installer_input)
    elif installer.suffix == ".sh":
        _run_installer_sh(installer, install_dir, installer_input=installer_input)
    elif installer.suffix == ".pkg":
        if request and ON_CI:
            request.addfinalizer(lambda: shutil.rmtree(str(install_dir)))
        _run_installer_pkg(installer, install_dir, example_path=example_path)
    else:
        raise ValueError(f"Unknown installer type: {installer.suffix}")
    if check_sentinels:
        _sentinel_file_checks(example_path, install_dir)
    if installer.suffix == ".exe":
        _run_uninstaller_exe(install_dir)


def create_installer(
    input_dir: Path,
    workspace: Path,
    conda_exe=CONSTRUCTOR_CONDA_EXE,
    debug=CONSTRUCTOR_DEBUG,
    with_spaces=False,
    **env_vars,
) -> Tuple[Path, Path]:
    if sys.platform.startswith("win") and conda_exe and _is_micromamba(conda_exe):
        pytest.skip("Micromamba is not supported on Windows yet (shortcut creation).")

    output_dir = workspace / "installer"
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        *COV_CMD,
        "constructor",
        "-v",
        str(input_dir),
        "--output-dir",
        str(output_dir),
    ]
    if conda_exe:
        cmd.extend(["--conda-exe", conda_exe])
    if debug:
        cmd.append("--debug")

    _execute(cmd, **env_vars)

    install_dir_prefix = "i n s t a l l" if with_spaces else "install"
    
    def _sort_by_extension(path):
        "Return shell installers first so they are run before the GUI ones"
        return {"sh": 1, "pkg": 2, "exe": 3}[path.suffix[1:]], path

    installers = (p for p in output_dir.iterdir() if p.suffix in (".exe", ".sh", ".pkg"))
    for installer in sorted(installers, key=_sort_by_extension):
        if installer.suffix == ".pkg" and ON_CI:
            install_dir = Path("~").expanduser() / calculate_install_dir(input_dir / "construct.yaml")
        else:
            install_dir = workspace / f"{install_dir_prefix}-{installer.stem}-{installer.suffix[1:]}"
        yield installer, install_dir
        if KEEP_ARTIFACTS_PATH:
            shutil.move(str(installer), str(KEEP_ARTIFACTS_PATH))


@lru_cache(maxsize=None)
def _self_signed_certificate(path: str, password: str = None):
    if not sys.platform.startswith("win"):
        return
    return _execute(
        ["powershell.exe", REPO_DIR / "scripts/create_self_signed_certificate.ps1"],
        CONSTRUCTOR_SIGNING_CERTIFICATE=str(path),
        CONSTRUCTOR_PFX_CERTIFICATE_PASSWORD=password,
    )


def _example_path(example_name):
    return REPO_DIR / "examples" / example_name


def _is_micromamba(path):
    return "micromamba" in Path(path).stem


def test_example_customize_controls(tmp_path, request):
    input_path = _example_path("customize_controls")
    for installer, install_dir in create_installer(input_path, tmp_path):
        _run_installer(input_path, installer, install_dir, request=request)


def test_example_customized_welcome_conclusion(tmp_path, request):
    input_path = _example_path("customized_welcome_conclusion")
    for installer, install_dir in create_installer(input_path, tmp_path):
        _run_installer(input_path, installer, install_dir, request=request)


def test_example_extra_envs(tmp_path, request):
    input_path = _example_path("extra_envs")
    for installer, install_dir in create_installer(input_path, tmp_path):
        _run_installer(input_path, installer, install_dir, request=request)


def test_example_extra_files(tmp_path, request):
    input_path = _example_path("extra_files")
    for installer, install_dir in create_installer(input_path, tmp_path, with_spaces=True):
        _run_installer(input_path, installer, install_dir, request=request)


def test_example_miniforge(tmp_path, request):
    input_path = _example_path("miniforge")
    for installer, install_dir in create_installer(input_path, tmp_path):
        if installer.suffix == ".sh":
            # try both batch and interactive installations
            install_dirs = install_dir / "batch", install_dir / "interactive"
            installer_inputs = None, f"\nyes\n{install_dir / 'interactive'}\nno\n"
        else:
            install_dirs = (install_dir,)
            installer_inputs = (None,)
        for installer_input, install_dir in zip(installer_inputs, install_dirs):
            _run_installer(
                input_path,
                installer,
                install_dir,
                installer_input=installer_input,
                # PKG installers use their own install path, so we can't check sentinels
                # via `install_dir`
                check_sentinels=installer.suffix != ".pkg",
            )
            if installer.suffix == ".pkg" and ON_CI:
                _sentinel_file_checks(input_path, Path(os.environ["HOME"]) / "Miniforge3")
    

def test_example_noconda(tmp_path, request):
    input_path = _example_path("noconda")
    for installer, install_dir in create_installer(input_path, tmp_path, with_spaces=True):
        _run_installer(input_path, installer, install_dir, request=request)


@pytest.mark.skipif(sys.platform != "Darwin", reason="macOS only")
def test_example_osxpkg(tmp_path, request):
    input_path = _example_path("osxpkg")
    for installer, install_dir in create_installer(input_path, tmp_path):
        _run_installer(input_path, installer, install_dir, request=request)


def test_example_scripts(tmp_path, request):
    input_path = _example_path("scripts")
    for installer, install_dir in create_installer(input_path, tmp_path, with_spaces=True):
        _run_installer(input_path, installer, install_dir, request=request)


def test_example_shortcuts(tmp_path, request):
    input_path = _example_path("shortcuts")
    for installer, install_dir in create_installer(input_path, tmp_path):
        _run_installer(input_path, installer, install_dir, request=request)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_example_signing(tmp_path, request):
    input_path = _example_path("signing")
    cert_path = tmp_path / "self-signed-cert.pfx"
    cert_pwd = "1234"
    _self_signed_certificate(path=cert_path, password=cert_pwd)
    assert cert_path.exists()
    certificate_in_input_dir = input_path / "certificate.pfx"
    shutil.copy(str(cert_path), str(certificate_in_input_dir))
    request.addfinalizer(lambda: certificate_in_input_dir.unlink())
    for installer, install_dir in create_installer(
        input_path,
        tmp_path,
        with_spaces=True,
        CONSTRUCTOR_SIGNING_CERTIFICATE=str(cert_path),
        CONSTRUCTOR_PFX_CERTIFICATE_PASSWORD=cert_pwd,
    ):
        _run_installer(input_path, installer, install_dir, request=request)


def test_example_use_channel_remap(tmp_path, request):
    input_path = _example_path("use_channel_remap")
    for installer, install_dir in create_installer(input_path, tmp_path):
        _run_installer(input_path, installer, install_dir, request=request)
