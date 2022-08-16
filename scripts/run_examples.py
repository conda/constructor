#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run examples bundled with this repo."""

# Standard library imports
import os
import subprocess
import sys
import tempfile
import platform
import shutil
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


def _execute(cmd):
    print(' '.join(cmd))
    p = subprocess.Popen(cmd, stderr=subprocess.PIPE)
    print('--- STDOUT ---')
    _, stderr = p.communicate()
    if stderr:
        print('--- STDERR ---')
        if PY3:
            stderr = stderr.decode()
        print(stderr.strip())
    return p.returncode != 0


def run_examples(keep_artifacts=None):
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

    parent_output = tempfile.mkdtemp()
    tested_files = set()
    for example_path in sorted(example_paths):
        print(example_path)
        print('-' * len(example_path))
        output_dir = tempfile.mkdtemp(dir=parent_output)
        cmd = COV_CMD + ['constructor', example_path, '--output-dir', output_dir]
        errored += _execute(cmd)
        for fpath in os.listdir(output_dir):
            ext = fpath.rsplit('.', 1)[-1]
            if fpath in tested_files or ext not in ('sh', 'exe', 'pkg'):
                continue
            tested_files.add(fpath)
            env_dir = tempfile.mkdtemp(dir=output_dir)
            rm_rf(env_dir)
            print('---- testing %s' % fpath)
            fpath = os.path.join(output_dir, fpath)
            if ext == 'sh':
                cmd = ['bash', fpath, '-b', '-p', env_dir]
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
                cmd = ['cmd.exe', '/c', 'start', '/wait', fpath, '/S', '/D=%s' % env_dir]
            test_errored = _execute(cmd)
            if ext == 'exe' and os.environ.get("NSIS_USING_LOG_BUILD"):
                test_errored = 0
                with open(os.path.join(env_dir, "install.log")) as f:
                    print('---  LOGS  ---')
                    for line in f:
                        print(line.rstrip())
                        if ":error:" in line:
                            test_errored = 1
            errored += test_errored
            if keep_artifacts:
                shutil.move(fpath, keep_artifacts)
            # more complete logs are available under /var/log/install.log
            if test_errored and ext == "pkg" and os.environ.get("CI"):
                print('---  LOGS  ---')
                print("Tip: Debug locally and check the full logs in the Installer UI")
                print("     or check /var/log/install.log if run from the CLI.")
        print('')

    if errored:
        print('Some examples failed!')
        print('Assets saved in: %s' % parent_output)
    else:
        print('All examples ran successfully!')
        shutil.rmtree(parent_output)
    return errored


if __name__ == '__main__':
    if len(sys.argv) >=2 and sys.argv[1].startswith('--keep-artifacts='):
        keep_artifacts = sys.argv[1].split("=")[1]
    else:
        keep_artifacts = None
    n_errors = run_examples(keep_artifacts)
    sys.exit(n_errors)
