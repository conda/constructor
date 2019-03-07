#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run examples bundled with this repo."""

# Standard library imports
import os
import subprocess
import sys
import platform

HERE = os.path.abspath(os.path.dirname(__file__))
REPO_DIR = os.path.dirname(HERE)
EXAMPLES_DIR = os.path.join(REPO_DIR, 'examples')
PY3 = sys.version_info[0] == 3
WHITELIST = ['grin', 'jetsonconda', 'maxiconda', 'newchan']
BLACKLIST = []

def run_examples():
    """Run examples bundled with the repository."""
    example_paths = []
    errored = 0

    if platform.system() != 'Darwin':
        BLACKLIST.append(os.path.join(EXAMPLES_DIR, "osxpkg"))

    whitelist = [os.path.join(EXAMPLES_DIR, p) for p in WHITELIST]
    for fname in os.listdir(EXAMPLES_DIR):
        fpath = os.path.join(EXAMPLES_DIR, fname)
        if os.path.isdir(fpath) and fpath not in whitelist and fpath not in BLACKLIST:
            example_paths.append(fpath)

    for i, example_path in enumerate(sorted(example_paths)):
        cmd = ['constructor', example_path]
        p = subprocess.Popen(cmd, stderr=subprocess.PIPE)
        print('\n\n# Testing example {}:\n--------------------'.format(i + 1))
        print(example_path)
        print('\n')
        stdout, stderr = p.communicate()
        if PY3:
            stderr = stderr.decode().strip()

        if p.returncode != 0:
            errored += 1
            print(stderr)

    if errored:
        print('\n\nSome examples failed!\n\n')
        sys.exit(1)
    else:
        print('\n\nAll examples ran successfully!\n\n')


if __name__ == '__main__':
    run_examples()
