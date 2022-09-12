#!/bin/bash
set -ex

# tests
# base environment uses python 3.7 and excludes tk
test -f "$PREFIX/conda-meta/history"
"$PREFIX/bin/python" -c "from sys import version_info; assert version_info[:2] == (3, 7)"
"$PREFIX/bin/pip" -V
# tk(inter) shouldn't be listed by conda!
"$PREFIX/bin/conda" list -p "$PREFIX" | jq -e '.[] | select(.name == "tk")' && exit 1
echo "Previous test failed as expected"

# extra env named 'py38' uses python 3.8, has tk, but we removed setuptools
test -f "$PREFIX/envs/py38/conda-meta/history"
"$PREFIX/envs/py38/bin/python" -c "from sys import version_info; assert version_info[:2] == (3, 8)"
# setuptools shouldn't be listed by conda!
"$PREFIX/bin/conda" list -p "$PREFIX/envs/py38" | jq -e '.[] | select(.name == "setuptools")' && exit 1
"$PREFIX/envs/py38/bin/python" -c "import setuptools" && exit 1
echo "Previous test failed as expected"

# this env only contains dav1d, no python; it should have been created with no errors,
# even if we had excluded tk from the package list
test -f "$PREFIX/envs/dav1d/conda-meta/history"
test ! -f "$PREFIX/envs/dav1d/bin/python"
"$PREFIX/envs/dav1d/bin/dav1d" --version
