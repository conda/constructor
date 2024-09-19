import getpass
import json
import os
import shutil
import subprocess
import sys
import time
import warnings
import xml.etree.ElementTree as ET
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from plistlib import load as plist_load
from typing import Generator, Iterable, Optional, Tuple

import pytest
from conda.base.context import context
from conda.core.prefix_data import PrefixData
from conda.models.version import VersionOrder as Version

from constructor.utils import identify_conda_exe

if sys.platform == "darwin":
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
CONDA_EXE, CONDA_EXE_VERSION = identify_conda_exe(CONSTRUCTOR_CONDA_EXE)
CONSTRUCTOR_DEBUG = bool(os.environ.get("CONSTRUCTOR_DEBUG"))
if artifacts_path := os.environ.get("CONSTRUCTOR_EXAMPLES_KEEP_ARTIFACTS"):
    KEEP_ARTIFACTS_PATH = Path(artifacts_path)
    KEEP_ARTIFACTS_PATH.mkdir(parents=True, exist_ok=True)
else:
    KEEP_ARTIFACTS_PATH = None


def _execute(
    cmd: Iterable[str], installer_input=None, check=True, timeout=420, **env_vars
) -> subprocess.CompletedProcess:
    t0 = time.time()
    # The environment is not copied on Windows, so copy here to get consistent behavior
    env = os.environ.copy()
    if env_vars:
        env.update({k: v for (k, v) in env_vars.items() if v is not None})
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
        stdout, stderr = p.communicate(input=installer_input, timeout=timeout)
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


def _check_installer_log(install_dir):
    # Windows installers won't raise exit codes so we need to check the log file
    error_lines = []
    try:
        log_is_empty = True
        with open(os.path.join(install_dir, "install.log"), encoding="utf-16-le") as f:
            print("Installer log:", file=sys.stderr)
            for line in f:
                log_is_empty = False
                print(line, end="", file=sys.stderr)
                if ":error:" in line.lower():
                    error_lines.append(line)
        if log_is_empty:
            error_lines.append("Logfile was unexpectedly empty!")
    except Exception as exc:
        error_lines.append(
            f"Could not read logs! {exc.__class__.__name__}: {exc}\n"
            "Did you install the 'log' variant of nsis? 'conda install conda-forge::nsis=*=*log*'\n"
            "Once you have installed it, set NSIS_USING_LOG_BUILD=1.\n"
            "Otherwise, this usually means that the destination folder could not be created.\n"
            "Possible causes: permissions, non-supported characters, long paths...\n"
            "Consider setting 'check_path_spaces' and 'check_path_length' to 'False'."
        )
    if error_lines:
        raise AssertionError("\n".join(error_lines))


def _run_installer_exe(installer, install_dir, installer_input=None, timeout=420, check=True):
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

    Note that we do print information to the console, but that's not the stdout stream
    of the subprocess. We make NSIS attach itself to the parent console and write directly there.
    As a result we can't capture the output, so we still have to rely on the logfiles.
    """
    if not sys.platform.startswith("win"):
        raise ValueError("Can only run .exe installers on Windows")
    if "NSIS_USING_LOG_BUILD" not in os.environ:
        warnings.warn(
            "Windows installers are tested with NSIS in silent mode, which does "
            "not report errors to stdout. You should use logging-enabled NSIS builds "
            "to generate an 'install.log' file this script will search for errors "
            "after completion."
        )
    cmd = ["cmd.exe", "/c", "start", "/wait", installer, "/S", *f"/D={install_dir}".split()]
    process = _execute(cmd, installer_input=installer_input, timeout=timeout, check=check)
    if check:
        _check_installer_log(install_dir)
    return process


def _run_uninstaller_exe(install_dir, timeout=420, check=True):
    # Now test the uninstallers
    if " " in str(install_dir):
        # TODO: We can't seem to run the uninstaller when there are spaces in the PATH
        warnings.warn(
            f"Skipping uninstaller tests for '{install_dir}' due to spaces in path. "
            "This is a known issue with our setup, to be fixed."
        )
        return
    # Rename install.log
    install_log = install_dir / "install.log"
    if install_log.exists():
        install_log.rename(install_dir / "install.log.bak")

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
    process = _execute(cmd, timeout=timeout, check=check)
    if check:
        _check_installer_log(install_dir)
        remaining_files = list(install_dir.iterdir())
        if len(remaining_files) > 3:
            # The debug installer writes to install.log too, which will only
            # be deleted _after_ a reboot. Finding some files is ok, but more
            # than two usually means a problem with the uninstaller.
            # Note this is is not exhaustive, because we are not checking
            # whether the registry was restored, menu items were deleted, etc.
            # TODO :)
            raise AssertionError(f"Uninstaller left too many files: {remaining_files}")
    return process


def _run_installer_sh(installer, install_dir, installer_input=None, timeout=420, check=True):
    if installer_input:
        cmd = ["/bin/sh", installer]
    else:
        cmd = ["/bin/sh", installer, "-b", "-p", install_dir]
    return _execute(cmd, installer_input=installer_input, timeout=timeout, check=check)


def _run_installer_pkg(
    installer,
    install_dir,
    example_path=None,
    config_filename="construct.yaml",
    timeout=420,
    check=True,
):
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
            install_dir = calculate_install_dir(example_path / config_filename)
            install_dir = Path(os.environ["HOME"]) / install_dir
    else:
        # This command only expands the PKG, but does not install
        warnings.warn(
            "Not running installer, only expanding the PKG. "
            "Export CI=1 to run it, but it will pollute your $HOME."
        )
        cmd = ["pkgutil", "--expand", installer, install_dir]
    return _execute(cmd, timeout=timeout, check=check), install_dir


def _sentinel_file_checks(example_path, install_dir):
    script_ext = "bat" if sys.platform.startswith("win") else "sh"
    for script_prefix in "pre", "post", "test":
        script = f"{script_prefix}_install.{script_ext}"
        sentinel = f"{script_prefix}_install_sentinel.txt"
        if (example_path / script).exists() and not (install_dir / sentinel).exists():
            raise AssertionError(
                f"Sentinel file for {script_prefix}_install not found! "
                f"{install_dir} contents:\n" + "\n".join(sorted(map(str, install_dir.iterdir())))
            )


def _run_installer(
    example_path: Path,
    installer: Path,
    install_dir: Path,
    installer_input: Optional[str] = None,
    config_filename="construct.yaml",
    check_sentinels=True,
    check_subprocess=True,
    request=None,
    uninstall=True,
    timeout=420,
) -> subprocess.CompletedProcess:
    if installer.suffix == ".exe":
        process = _run_installer_exe(
            installer,
            install_dir,
            installer_input=installer_input,
            timeout=timeout,
            check=check_subprocess,
        )
    elif installer.suffix == ".sh":
        process = _run_installer_sh(
            installer,
            install_dir,
            installer_input=installer_input,
            timeout=timeout,
            check=check_subprocess,
        )
    elif installer.suffix == ".pkg":
        if request and ON_CI:
            request.addfinalizer(lambda: shutil.rmtree(str(install_dir), ignore_errors=True))
        process, _ = _run_installer_pkg(
            installer,
            install_dir,
            example_path=example_path,
            config_filename=config_filename,
            timeout=timeout,
            check=check_subprocess,
        )
    else:
        raise ValueError(f"Unknown installer type: {installer.suffix}")
    if check_sentinels:
        _sentinel_file_checks(example_path, install_dir)
    if uninstall and installer.suffix == ".exe":
        _run_uninstaller_exe(install_dir, timeout=timeout, check=check_subprocess)
    return process


def create_installer(
    input_dir: Path,
    workspace: Path,
    conda_exe=CONSTRUCTOR_CONDA_EXE,
    debug=CONSTRUCTOR_DEBUG,
    with_spaces=False,
    timeout=420,
    config_filename="construct.yaml",
    extra_constructor_args: Iterable[str] = None,
    **env_vars,
) -> Generator[Tuple[Path, Path], None, None]:
    if sys.platform.startswith("win") and conda_exe and _is_micromamba(conda_exe):
        pytest.skip("Micromamba is not supported on Windows yet.")

    output_dir = workspace / "installer"
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        *COV_CMD,
        "constructor",
        "-v",
        str(input_dir),
        "--output-dir",
        str(output_dir),
        "--config-filename",
        config_filename,
    ]
    if conda_exe:
        cmd.extend(["--conda-exe", conda_exe])
    if debug:
        cmd.append("--debug")
    if extra_constructor_args:
        cmd.extend(extra_constructor_args)

    _execute(cmd, timeout=timeout, **env_vars)

    install_dir_prefix = "i n s t a l l" if with_spaces else "install"

    def _sort_by_extension(path):
        "Return shell installers first so they are run before the GUI ones"
        return {"sh": 1, "pkg": 2, "exe": 3}[path.suffix[1:]], path

    installers = (p for p in output_dir.iterdir() if p.suffix in (".exe", ".sh", ".pkg"))
    for installer in sorted(installers, key=_sort_by_extension):
        if installer.suffix == ".pkg" and ON_CI:
            install_dir = Path("~").expanduser() / calculate_install_dir(
                input_dir / config_filename
            )
        else:
            install_dir = (
                workspace / f"{install_dir_prefix}-{installer.stem}-{installer.suffix[1:]}"
            )
        yield installer, install_dir
        if KEEP_ARTIFACTS_PATH:
            shutil.move(str(installer), str(KEEP_ARTIFACTS_PATH))


@lru_cache(maxsize=None)
def _self_signed_certificate_windows(path: str, password: str = None):
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


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_example_extra_pages_win(tmp_path, request):
    input_path = _example_path("exe_extra_pages")
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


@pytest.mark.xfail(
    CONDA_EXE == "conda-standalone" and Version(CONDA_EXE_VERSION) < Version("23.11.0a0"),
    reason="Known issue with conda-standalone<=23.10: shortcuts are created but not removed.",
)
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
                uninstall=False,
            )
            if installer.suffix == ".pkg" and ON_CI:
                _sentinel_file_checks(input_path, Path(os.environ["HOME"]) / "Miniforge3")
            if installer.suffix == ".exe":
                for key in ("ProgramData", "AppData"):
                    start_menu_dir = Path(
                        os.environ[key],
                        "Microsoft/Windows/Start Menu/Programs/Miniforge3",
                    )
                    if start_menu_dir.is_dir():
                        assert list(start_menu_dir.glob("Miniforge*.lnk"))
                        break
                else:
                    raise AssertionError("Could not find Start Menu folder for miniforge")
                _run_uninstaller_exe(install_dir)
                assert not list(start_menu_dir.glob("Miniforge*.lnk"))


def test_example_noconda(tmp_path, request):
    input_path = _example_path("noconda")
    for installer, install_dir in create_installer(
        input_path, tmp_path, config_filename="constructor_input.yaml", with_spaces=True
    ):
        _run_installer(
            input_path,
            installer,
            install_dir,
            config_filename="constructor_input.yaml",
            request=request,
        )


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_example_osxpkg(tmp_path, request):
    input_path = _example_path("osxpkg")
    ownership_test_files_home = [
        ".bash_profile",
        ".conda",
        ".condarc",
        ".config",
        ".config/fish",
        ".config/fish/fish.config",
        ".config/powershell",
        ".config/powershell/profile.ps1",
        ".tcshrc",
        ".xonshrc",
        ".zshrc",
    ]
    ownership_test_files_home = [Path.home() / file for file in ownership_test_files_home]
    # getpass.getuser is more reliable than os.getlogin:
    # https://docs.python.org/3/library/os.html#os.getlogin
    expected_owner = getpass.getuser()
    for installer, install_dir in create_installer(input_path, tmp_path):
        _run_installer(input_path, installer, install_dir, request=request)
        expected = {}
        found = {}
        for file in ownership_test_files_home:
            if not file.exists():
                continue
            expected[file] = expected_owner
            found[file] = file.owner()
        assert expected == found


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
@pytest.mark.skipif(not shutil.which("xcodebuild"), reason="requires xcodebuild")
def test_example_osxpkg_extra_pages(tmp_path):
    try:
        subprocess.run(["xcodebuild", "--help"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        pytest.skip("xcodebuild requires XCode to compile extra pages.")
    recipe_path = _example_path("osxpkg_extra_pages")
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"
    shutil.copytree(str(recipe_path), str(input_path))
    installer, install_dir = next(create_installer(input_path, output_path))
    # expand-full is an undocumented option that extracts all archives,
    # including binary archives like the PlugIns file
    cmd = ["pkgutil", "--expand-full", installer, output_path / "expanded"]
    _execute(cmd)
    installer_sections = output_path / "expanded" / "PlugIns" / "InstallerSections.plist"
    assert installer_sections.exists()

    with open(installer_sections, "rb") as f:
        plist = plist_load(f)
    expected = {
        "SectionOrder": [
            "Introduction",
            "ReadMe",
            "License",
            "Target",
            "PackageSelection",
            "Install",
            "ExtraPage.bundle",
        ]
    }
    assert plist == expected


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
@pytest.mark.skipif(not shutil.which("xcodebuild"), reason="requires xcodebuild")
@pytest.mark.skipif("CI" not in os.environ, reason="CI only")
def test_macos_signing(tmp_path, self_signed_application_certificate_macos):
    try:
        subprocess.run(["xcodebuild", "--help"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        pytest.skip("xcodebuild requires XCode to compile extra pages.")
    input_path = tmp_path / "input"
    recipe_path = _example_path("osxpkg_extra_pages")
    shutil.copytree(str(recipe_path), str(input_path))
    with open(input_path / "construct.yaml", "a") as f:
        f.write(f"notarization_identity_name: {self_signed_application_certificate_macos}\n")
    output_path = tmp_path / "output"
    installer, install_dir = next(create_installer(input_path, output_path))

    # Check component signatures
    expanded_path = output_path / "expanded"
    # expand-full is an undocumented option that extracts all archives,
    # including binary archives like the PlugIns file
    cmd = ["pkgutil", "--expand-full", installer, expanded_path]
    _execute(cmd)
    components = [
        Path(expanded_path, "prepare_installation.pkg", "Payload", "osx-pkg-test", "_conda"),
        Path(expanded_path, "Plugins", "ExtraPage.bundle"),
    ]
    validated_signatures = []
    for component in components:
        p = subprocess.run(
            ["/usr/bin/codesign", "--verify", str(component), "--verbose=4"],
            check=True,
            text=True,
            capture_output=True,
        )
        # codesign --verify outputs to stderr
        lines = p.stderr.split("\n")[:-1]
        if (
            len(lines) == 2
            and lines[0] == f"{component}: valid on disk"
            and lines[1] == f"{component}: satisfies its Designated Requirement"
        ):
            validated_signatures.append(component)
    assert validated_signatures == components


def test_example_scripts(tmp_path, request):
    input_path = _example_path("scripts")
    for installer, install_dir in create_installer(input_path, tmp_path, with_spaces=True):
        _run_installer(input_path, installer, install_dir, request=request)


@pytest.mark.skipif(
    CONDA_EXE == "micromamba" or Version(CONDA_EXE_VERSION) < Version("23.11.0a0"),
    reason="menuinst v2 requires conda-standalone>=23.11.0; micromamba is not supported yet",
)
def test_example_shortcuts(tmp_path, request):
    input_path = _example_path("shortcuts")
    for installer, install_dir in create_installer(input_path, tmp_path):
        _run_installer(input_path, installer, install_dir, request=request, uninstall=False)
        # check that the shortcuts are created
        if sys.platform == "win32":
            for key in ("ProgramData", "AppData"):
                start_menu = Path(os.environ[key]) / "Microsoft/Windows/Start Menu/Programs"
                package_1 = start_menu / "Package 1"
                anaconda = start_menu / "Anaconda3 (64-bit)"
                if package_1.is_dir() and anaconda.is_dir():
                    assert (package_1 / "A.lnk").is_file()
                    assert (package_1 / "B.lnk").is_file()
                    # The shortcut created from the 'base' env
                    # should not exist because we filtered it out in the YAML
                    # We do expect one shortcut from 'another_env'
                    assert not (anaconda / "Anaconda Prompt.lnk").is_file()
                    assert (anaconda / "Anaconda Prompt (another_env).lnk").is_file()
                    break
            else:
                raise AssertionError("No shortcuts found!")
            _run_uninstaller_exe(install_dir)
            assert not (package_1 / "A.lnk").is_file()
            assert not (package_1 / "B.lnk").is_file()
        elif sys.platform == "darwin":
            applications = Path("~/Applications").expanduser()
            print("Shortcuts found:", sorted(applications.glob("**/*.app")))
            assert (applications / "A.app").exists()
            assert (applications / "B.app").exists()
        elif sys.platform == "linux":
            applications = Path("~/.local/share/applications").expanduser()
            print("Shortcuts found:", sorted(applications.glob("**/*.desktop")))
            assert (applications / "package-1_a.desktop").exists()
            assert (applications / "package-1_b.desktop").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_example_signing(tmp_path, request):
    input_path = _example_path("signing")
    cert_path = tmp_path / "self-signed-cert.pfx"
    cert_pwd = "1234"
    _self_signed_certificate_windows(path=cert_path, password=cert_pwd)
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


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
@pytest.mark.skipif(
    not shutil.which("azuresigntool") and not os.environ.get("AZURE_SIGNTOOL_PATH"),
    reason="AzureSignTool not available",
)
@pytest.mark.parametrize(
    "auth_method",
    os.environ.get("AZURE_SIGNTOOL_TEST_AUTH_METHODS", "token,secret").split(","),
)
def test_azure_signtool(tmp_path, request, monkeypatch, auth_method):
    """Test signing installers with AzureSignTool.

    There are three ways to authenticate with Azure: tokens, secrets, and managed identities.
    There is no good sentinel environment for manged identities, so an environment variable
    is used to determine which authentication methods to test.
    """
    if auth_method == "token":
        if not os.environ.get("AZURE_SIGNTOOL_KEY_VAULT_ACCESSTOKEN"):
            pytest.skip("No AzureSignTool token in environment.")
        monkeypatch.delenv("AZURE_SIGNTOOL_KEY_VAULT_SECRET", raising=False)
    elif auth_method == "secret":
        if not os.environ.get("AZURE_SIGNTOOL_KEY_VAULT_SECRET"):
            pytest.skip("No AzureSignTool secret in environment.")
        monkeypatch.delenv("AZURE_SIGNTOOL_KEY_VAULT_ACCESSTOKEN", raising=False)
    elif auth_method == "managed":
        monkeypatch.delenv("AZURE_SIGNTOOL_KEY_VAULT_ACCESSTOKEN", raising=False)
        monkeypatch.delenv("AZURE_SIGNTOOL_KEY_VAULT_SECRET", raising=False)
    else:
        pytest.skip(f"Unknown authentication method {auth_method}.")
    input_path = _example_path("azure_signtool")
    for installer, install_dir in create_installer(
        input_path,
        tmp_path,
    ):
        _run_installer(input_path, installer, install_dir, request=request)


def test_example_use_channel_remap(tmp_path, request):
    input_path = _example_path("use_channel_remap")
    for installer, install_dir in create_installer(input_path, tmp_path):
        _run_installer(input_path, installer, install_dir, request=request, uninstall=False)
        p = subprocess.run(
            [sys.executable, "-m", "conda", "list", "--prefix", install_dir, "--json"],
            capture_output=True,
            text=True,
        )
        packages = json.loads(p.stdout)
        for pkg in packages:
            assert pkg["channel"] == "private_repo"


def test_example_from_existing_env(tmp_path, request):
    input_path = _example_path("from_existing_env")
    subprocess.check_call(
        [sys.executable, "-mconda", "create", "-p", tmp_path / "env", "-y", "python"]
    )
    for installer, install_dir in create_installer(
        input_path,
        tmp_path,
        CONSTRUCTOR_TEST_EXISTING_ENV=str(tmp_path / "env"),
    ):
        _run_installer(input_path, installer, install_dir, request=request)
        if installer.suffix == ".pkg" and not ON_CI:
            return
        for pkg in PrefixData(install_dir, pip_interop_enabled=True).iter_records():
            assert pkg["channel"] != "pypi"


def test_example_from_env_txt(tmp_path, request):
    input_path = _example_path("from_env_txt")
    for installer, install_dir in create_installer(input_path, tmp_path):
        _run_installer(input_path, installer, install_dir, request=request)
        if installer.suffix == ".pkg" and not ON_CI:
            return
        for pkg in PrefixData(install_dir, pip_interop_enabled=True).iter_records():
            assert pkg["channel"] != "pypi"


def test_example_from_env_yaml(tmp_path, request):
    input_path = _example_path("from_env_yaml")
    for installer, install_dir in create_installer(input_path, tmp_path, timeout=600):
        _run_installer(input_path, installer, install_dir, request=request)
        if installer.suffix == ".pkg" and not ON_CI:
            return
        for pkg in PrefixData(install_dir, pip_interop_enabled=True).iter_records():
            assert pkg["channel"] != "pypi"


@pytest.mark.skipif(context.subdir != "linux-64", reason="Linux x64 only")
def test_example_from_explicit(tmp_path, request):
    input_path = _example_path("from_explicit")
    for installer, install_dir in create_installer(input_path, tmp_path):
        _run_installer(input_path, installer, install_dir, request=request)
        if installer.suffix == ".pkg" and not ON_CI:
            return
        out = subprocess.check_output(
            [sys.executable, "-mconda", "list", "-p", install_dir, "--explicit", "--md5"],
            text=True,
        )
        assert out == (input_path / "explicit_linux-64.txt").read_text()


def test_register_envs(tmp_path, request):
    input_path = _example_path("register_envs")
    for installer, install_dir in create_installer(input_path, tmp_path):
        _run_installer(input_path, installer, install_dir, request=request)
        environments_txt = Path("~/.conda/environments.txt").expanduser().read_text()
        assert str(install_dir) not in environments_txt


@pytest.mark.skipif(sys.platform != "darwin", reason="MacOS only")
@pytest.mark.parametrize("domains", ({}, {"enable_anywhere": "false", "enable_localSystem": True}))
def test_pkg_distribution_domains(tmp_path, domains):
    recipe_path = _example_path("osxpkg")
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"
    shutil.copytree(str(recipe_path), str(input_path))
    if domains:
        with open(input_path / "construct.yaml", "a") as cyml:
            cyml.write("pkg_domains:\n")
            for key, val in domains.items():
                cyml.write(f"  {key}: {val}\n")

    installer, install_dir = next(create_installer(input_path, output_path))
    cmd = ["pkgutil", "--expand", installer, output_path / "expanded"]
    _execute(cmd)
    domains_file = output_path / "expanded" / "Distribution"
    assert domains_file.exists()

    tree = ET.parse(domains_file)
    found = {key: val for key, val in tree.find("domains").items()}
    defaults = {"enable_anywhere": "true", "enable_currentUserHome": "true"}
    expected = {key: str(val).lower() for key, val in domains.items()} if domains else defaults
    assert expected == found


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_cross_osx_building(tmp_path):
    input_path = _example_path("noconda")
    tmp_env = tmp_path / "env"
    subprocess.check_call(
        [
            sys.executable,
            "-mconda",
            "create",
            "-p",
            tmp_env,
            "-y",
            "micromamba",
            "--platform",
            "osx-arm64",
        ],
    )
    micromamba_arm64 = tmp_env / "bin" / "micromamba"
    create_installer(
        input_path,
        tmp_path,
        conda_exe=micromamba_arm64,
        extra_constructor_args=["--platform", "osx-arm64"],
        config_filename="constructor_input.yaml",
    )


def test_virtual_specs_failed(tmp_path, request):
    input_path = _example_path("virtual_specs_failed")
    for installer, install_dir in create_installer(input_path, tmp_path):
        process = _run_installer(
            input_path,
            installer,
            install_dir,
            request=request,
            check_subprocess=False,
            uninstall=False,
        )
        # This example is configured to fail due to unsatisfiable virtual specs
        if installer.suffix == ".exe":
            with pytest.raises(AssertionError, match="Failed to check virtual specs"):
                _check_installer_log(install_dir)
            continue
        elif installer.suffix == ".pkg":
            # The GUI does provide a better message with the min version and so on
            # but on the CLI we fail with this one instead
            msg = "Cannot install on volume"
        else:
            # The shell installer has its own Bash code for __glibc and __osx
            # Other virtual specs like __cuda are checked by conda-standalone/micromamba
            # and will fail with solver errors like PackagesNotFound etc
            msg = "Installer requires"
        assert process.returncode != 0
        assert msg in process.stdout + process.stderr


def test_virtual_specs_ok(tmp_path, request):
    input_path = _example_path("virtual_specs_ok")
    for installer, install_dir in create_installer(input_path, tmp_path):
        _run_installer(
            input_path,
            installer,
            install_dir,
            request=request,
            check_subprocess=True,
            uninstall=True,
        )


@pytest.mark.xfail(
    CONDA_EXE == "conda-standalone" and Version(CONDA_EXE_VERSION) < Version("24.9.0"),
    reason="Pre-existing .condarc breaks installation",
)
def test_ignore_condarc_files(tmp_path, monkeypatch, request):
    # Create a bogus .condarc file that would result in errors if read.
    # conda searches inside XDG_CONFIG_HOME on all systems, which is a
    # a safer directory to monkeypatch, especially on Windows where patching
    # HOME or USERPROFILE breaks installer builds.
    # mamba does not search this directory, so use HOME as a fallback.
    # Since micromamba is not supported on Windows, this is not a problem.
    if CONDA_EXE == "micromamba":
        monkeypatch.setenv("HOME", str(tmp_path))
        condarc = tmp_path / ".condarc"
    else:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        condarc = tmp_path / "conda" / ".condarc"
    condarc.parent.mkdir(parents=True, exist_ok=True)
    condarc.write_text("safety_checks:\n  - very safe\n")
    recipe_path = _example_path("customize_controls")
    input_path = tmp_path / "input"
    shutil.copytree(str(recipe_path), str(input_path))
    # Rewrite installer name to avoid duplicate artifacts
    construct_yaml = input_path / "construct.yaml"
    content = construct_yaml.read_text()
    construct_yaml.write_text(content.replace("name: NoCondaOptions", "name: NoCondaRC"))
    for installer, install_dir in create_installer(input_path, tmp_path):
        proc = _run_installer(
            input_path,
            installer,
            install_dir,
            request=request,
            check_subprocess=True,
            uninstall=True,
        )
        if CONDA_EXE == "micromamba" and installer.suffix == ".sh":
            # micromamba loads the rc files even for constructor subcommands.
            # This cannot be turned off with --no-rc, which causes four errors
            # in stderr. If there are more, other micromamba calls have read
            # the bogus .condarc file.
            # pkg installers unfortunately do not output any errors into the log.
            assert proc.stderr.count("Bad conversion of configurable") == 4
