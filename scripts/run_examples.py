#!/usr/bin/env python
"""Run examples bundled with this repo."""
import os
import sys
import tempfile
import platform
import shutil
from itertools import product
from subprocess import PIPE, Popen

from constructor.utils import rm_rf
from ruamel_yaml import round_trip_load, round_trip_dump

try:
    import coverage # noqa
    COV_CMD = ['coverage', 'run', '--append', '-m']
except ImportError:
    COV_CMD = []


HERE = os.path.abspath(os.path.dirname(__file__))
REPO_DIR = os.path.dirname(HERE)
EXAMPLES_DIR = os.path.join(REPO_DIR, 'examples')
PY3 = sys.version_info[0] == 3
WHITELIST = ['grin', 'jetsonconda', 'maxiconda', 'newchan']
BLACKLIST = []


def _execute(cmd):
    print(' '.join(cmd))
    p = Popen(cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    print('--- STDOUT ---')
    stdout, stderr = p.communicate()
    print(stdout.strip())
    if stderr:
        print('--- STDERR ---')
        print(stderr.strip())
    return p.returncode != 0, stdout.strip()


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
    conda_exes = [None]
    if platform.system() != 'Windows':
        env_name = "constructor-testing-micromamba"
        which_cmd = ["conda", "run", "--name", env_name, "which", "micromamba"]
        errored, micromamba_path = _execute(which_cmd)
        if errored:
            _execute(["conda", "create", "--name", env_name, "--yes", "-c", "conda-forge", "micromamba"])
            errored, micromamba_path = _execute(which_cmd)
            if errored:
                raise NotImplementedError("Failed to find micromamba")
        print("Found micromamba at:", micromamba_path)
        conda_exes += [micromamba_path]

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
    for example_path, conda_exe in product(sorted(example_paths), conda_exes):
        print(example_path)
        print('-' * len(example_path))
        output_dir = tempfile.mkdtemp(dir=parent_output)
        input_dir = os.path.join(output_dir, "input-files")
        cmd = COV_CMD + ['constructor', input_dir, '--output-dir', output_dir]

        # Copy the input to a temporary directory so we can modify it if needed
        shutil.copytree(example_path, input_dir)
        if conda_exe:
            with open(os.path.join(input_dir, "construct.yaml")) as fp:
                data = round_trip_load(fp)
            data["name"] = f"{data['name']}-{os.path.basename(conda_exe)}"
            with open(os.path.join(input_dir, "construct.yaml"), "wt") as fp:
                round_trip_dump(data, fp)
            print("Setting conda.exe to:", conda_exe)
            cmd += ['--conda-exe', conda_exe]

        # Create the installer
        errored += _execute(cmd)[0]
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
                # TODO: figure out how to do a command-line install
                # to an arbitrary directory. No luck yet. For now
                # we just expand it out
                cmd = ['pkgutil', '--expand', fpath, env_dir]
            elif ext == 'exe':
                cmd = ['cmd.exe', '/c', 'start', '/wait', fpath, '/S', '/D=%s' % env_dir]
            errored += _execute(cmd)[0]
            if keep_artifacts:
                shutil.move(fpath, keep_artifacts)
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
