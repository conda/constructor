#!/bin/bash
set -ex

# if PREFIX is not defined, then this was called from an OSX PKG installer
# $2 is the install location, ($HOME by default)
if [ -z "${PREFIX:-}" ]; then
    PREFIX=$(cd "$2/__NAME_LOWER__"; pwd)
fi

# tests
# base environment uses python 3.9 and excludes tk
test -f "$PREFIX/conda-meta/history"
"$PREFIX/bin/python" -c "from sys import version_info; assert version_info[:2] == (3, 9)"
# we use python -m pip instead of the pip entry point
# because the spaces break the shebang - this will be fixed
# with a new conda release, but for now this is the workaround
# we need. same with conda in the block below!
"$PREFIX/bin/python" -m pip -V
# tk(inter) shouldn't be listed by conda!
"$PREFIX/bin/python" -m conda list -p "$PREFIX" | grep tk && exit 1
echo "Previous test failed as expected"

# extra env named 'py310' uses python 3.10, has tk, but we removed setuptools
test -f "$PREFIX/envs/py310/conda-meta/history"
"$PREFIX/envs/py310/bin/python" -c "from sys import version_info; assert version_info[:2] == (3, 10)"
# setuptools shouldn't be listed by conda!
"$PREFIX/bin/python" -m conda list -p "$PREFIX/envs/py310" | grep setuptools && exit 1
"$PREFIX/envs/py310/bin/python" -c "import setuptools" && exit 1
echo "Previous test failed as expected"

# this env only contains dav1d, no python; it should have been created with no errors,
# even if we had excluded tk from the package list
test -f "$PREFIX/envs/dav1d/conda-meta/history"
test ! -f "$PREFIX/envs/dav1d/bin/python"
"$PREFIX/envs/dav1d/bin/dav1d" --version
