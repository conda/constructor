#!/usr/bin/env python
"""Run examples bundled with this repo."""
import argparse
import os
import subprocess
import sys
import tempfile
import platform
import shutil
import time
from datetime import timedelta
from pathlib import Path

from constructor.utils import rm_rf

try:
    import coverage # noqa
    COV_CMD = ['coverage', 'run', '--append', '-m']
except ImportError:
    COV_CMD = []


HERE = os.path.abspath(os.path.dirname(__file__))
REPO_DIR = os.path.dirname(HERE)
EXAMPLES_DIR = os.path.join(REPO_DIR, 'examples')
PY3 = sys.version_info[0] == 3
WHITELIST = ['grin', 'jetsonconda', 'miniconda', 'newchan']
BLACKLIST = []
WITH_SPACES = {"extra_files", "noconda", "signing", "scripts"}


def _execute(cmd, **env_vars):
    print(' '.join(cmd))
    t0 = time.time()
    if env_vars:
        env = os.environ.copy()
        env.update(env_vars)
    else:
        env = None
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    try:
        stdout, stderr = p.communicate(timeout=420)
        errored = p.returncode != 0
    except subprocess.TimeoutExpired:
        p.kill()
        stdout, stderr = p.communicate()
        print('--- TEST TIMEOUT ---')
        errored = True
    t1 = time.time()
    if errored or "CONDA_VERBOSITY" in env_vars:
        if stdout:
            print('--- STDOUT ---')
            print(stdout)
        if stderr:
            print('--- STDERR ---')
            print(stderr)
    print('--- Done in', timedelta(seconds=t1 - t0))
    return errored


def run_examples(keep_artifacts=None, conda_exe=None, debug=False):
    """Run examples bundled with the repository.

    Parameters
    ----------
    keep_artifacts: str, optional=None
        Path where the generated installers will be moved to.
        Will be created if it doesn't exist.

    Returns
    -------
    int
        Number of failed examples
    """
    if sys.platform.startswith("win") and "NSIS_USING_LOG_BUILD" not in os.environ:
        print(
            "! Warning !"
            "  Windows installers are tested with NSIS in silent mode, which does"
            "  not report errors on exit. You should use logging-enabled NSIS builds"
            "  to generate an 'install.log' file this script will search for errors"
            "  after completion."
        )
    example_paths = []
    errored = 0
    if platform.system() != 'Darwin':
        BLACKLIST.append(os.path.join(EXAMPLES_DIR, "osxpkg"))
    if keep_artifacts:
        os.makedirs(keep_artifacts, exist_ok=True)

    whitelist = [os.path.join(EXAMPLES_DIR, p) for p in WHITELIST]
    for fname in os.listdir(EXAMPLES_DIR):
        fpath = os.path.join(EXAMPLES_DIR, fname)
        if os.path.isdir(fpath) and fpath not in whitelist and fpath not in BLACKLIST:
            if os.path.exists(os.path.join(fpath, 'construct.yaml')):
                example_paths.append(fpath)

    # NSIS won't error out when running scripts unless we set this custom environment variable
    os.environ["NSIS_SCRIPTS_RAISE_ERRORS"] = "1"

    parent_output = tempfile.mkdtemp()
    tested_files = set()
    which_errored = {}
    for example_path in sorted(example_paths):
        example_name = Path(example_path).name
        test_with_spaces = example_name in WITH_SPACES
        print(example_name)
        print('-' * len(example_name))

        output_dir = tempfile.mkdtemp(prefix=f"{example_name}-", dir=parent_output)
        # resolve path to avoid some issues with TEMPDIR on Windows
        output_dir = str(Path(output_dir).resolve())
        cmd = COV_CMD + ['constructor', '-v', example_path, '--output-dir', output_dir]
        if conda_exe:
            cmd += ['--conda-exe', conda_exe]
        if debug:
            cmd.append("--debug")
        creation_errored = _execute(cmd)
        errored += creation_errored
        for fpath in os.listdir(output_dir):
            ext = fpath.rsplit('.', 1)[-1]
            if fpath in tested_files or ext not in ('sh', 'exe', 'pkg'):
                continue
            tested_files.add(fpath)
            test_suffix = "s p a c e s" if test_with_spaces else None
            env_dir = tempfile.mkdtemp(suffix=test_suffix, dir=output_dir)
            rm_rf(env_dir)
            fpath = os.path.join(output_dir, fpath)
            print('--- Testing', os.path.basename(fpath))
            if ext == 'sh':
                cmd = ['/bin/sh', fpath, '-b', '-p', env_dir]
            elif ext == 'pkg':
                if os.environ.get("CI"):
                    # We want to run it in an arbitrary directory, but the options
                    # are limited here... We can only install to $HOME :shrug:
                    # but that will pollute ~, so we only do it if we are running on CI
                    cmd = ['installer', '-pkg', fpath, '-dumplog',
                           '-target', 'CurrentUserHomeDirectory']
                else:
                    # This command only expands the PKG, but does not install
                    cmd = ['pkgutil', '--expand', fpath, env_dir]
            elif ext == 'exe':
                # NSIS manual:
                # > /D sets the default installation directory ($INSTDIR), overriding InstallDir
                # > and InstallDirRegKey. It must be the last parameter used in the command line
                # > and must not contain any quotes, even if the path contains spaces. Only
                # > absolute paths are supported.
                # Since subprocess.Popen WILL escape the spaces with quotes, we need to provide
                # them as separate arguments. We don't care about multiple spaces collapsing into
                # one, since the point is to just have spaces in the installation path -- one
                # would be enough too :)
                # This is why we have this weird .split() thingy down here:
                cmd = ['cmd.exe', '/c', 'start', '/wait', fpath, '/S', *f'/D={env_dir}'.split()]
            env = {"CONDA_VERBOSITY": "3"} if debug else {}
            test_errored = _execute(cmd, **env)
            # Windows EXEs never throw a non-0 exit code, so we need to check the logs,
            # which are only written if a special NSIS build is used
            win_error_lines = []
            if ext == 'exe' and os.environ.get("NSIS_USING_LOG_BUILD"):
                test_errored = 0
                try:
                    log_is_empty = True
                    with open(os.path.join(env_dir, "install.log"), encoding="utf-16-le") as f:
                        for line in f:
                            log_is_empty = False
                            if ":error:" in line:
                                win_error_lines.append(line)
                                test_errored = 1
                    if log_is_empty:
                        test_errored = 1
                        win_error_lines.append("Logfile was unexpectedly empty!")
                except Exception as exc:
                    test_errored = 1
                    win_error_lines.append(
                        f"Could not read logs! {exc.__class__.__name__}: {exc}\n"
                        "This usually means that the destination folder could not be created.\n"
                        "Possible causes: permissions, non-supported characters, long paths...\n"
                        "Consider setting 'check_path_spaces' and 'check_path_length' to 'False'."
                        )
            errored += test_errored
            if test_errored:
                which_errored.setdefault(example_path, []).append(fpath)
                if win_error_lines:
                    print('---  LOGS  ---')
                    for line in win_error_lines:
                        print(line.rstrip())
                if ext == "pkg" and os.environ.get("CI"):
                    # more complete logs are available under /var/log/install.log
                    print('---  LOGS  ---')
                    print("Tip: Debug locally and check the full logs in the Installer UI")
                    print("     or check /var/log/install.log if run from the CLI.")
            elif ext == "exe" and not test_with_spaces:
                # The installer succeeded, test the uninstaller on Windows
                # The un-installers are only tested when testing without spaces, as they hang during
                # testing but work in UI mode.
                uninstaller = next(
                    (p for p in os.listdir(env_dir) if p.startswith("Uninstall-")), None
                )
                if uninstaller:
                    cmd = [
                        'cmd.exe', '/c', 'start', '/wait',
                        os.path.join(env_dir, uninstaller),
                        # We need silent mode + "uninstaller location" (_?=...) so the command can
                        # be waited; otherwise, since the uninstaller copies itself to a different
                        # location so it can be auto-deleted, it returns immediately and it gives
                        # us problems with the tempdir cleanup later
                        f"/S _?={env_dir}"
                    ]
                    test_errored = _execute(cmd)
                    errored += test_errored
                    if test_errored:
                        which_errored.setdefault(example_path, []).append(
                            "Wrong uninstall exit code or timeout."
                        )
                    paths_after_uninstall = os.listdir(env_dir)
                    if len(paths_after_uninstall) > 2:
                        # The debug installer writes to install.log too, which will only
                        # be deleted _after_ a reboot. Finding some files is ok, but more
                        # than two usually means a problem with the uninstaller.
                        # Note this is is not exhaustive, because we are not checking
                        # whether the registry was restored, menu items were deleted, etc.
                        # TODO :)
                        which_errored.setdefault(example_path, []).append(
                            "Uninstaller left too many files behind!\n - "
                            "\n - ".join(paths_after_uninstall)
                        )
                else:
                    which_errored.setdefault(example_path, []).append("Could not find uninstaller!")

            if keep_artifacts:
                dest = os.path.join(keep_artifacts, os.path.basename(fpath))
                if os.path.isfile(dest):
                    os.unlink(dest)
                shutil.move(fpath, keep_artifacts)
        if creation_errored:
            which_errored.setdefault(example_path, []).append("Could not create installer!")
        print()

    print("-------------------------------")
    if errored:
        print('Some examples failed:')
        for installer, reasons in which_errored.items():
            print(f"+ {os.path.basename(installer)}")
            for reason in reasons:
                print(f"---> {reason}")
        print('Assets saved in:', keep_artifacts or parent_output)
    else:
        print('All examples ran successfully!')
        shutil.rmtree(parent_output)
    return errored


def cli():
    p = argparse.ArgumentParser()
    p.add_argument("--keep-artifacts")
    p.add_argument("--conda-exe")
    p.add_argument("--debug", action="store_true", default=False)
    return p.parse_args()


if __name__ == '__main__':
    args = cli()
    if args.conda_exe:
        assert os.path.isfile(args.conda_exe)
    n_errors = run_examples(
        keep_artifacts=args.keep_artifacts,
        conda_exe=args.conda_exe,
        debug=args.debug
    )
    sys.exit(n_errors)
