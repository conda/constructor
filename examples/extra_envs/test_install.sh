#!/bin/bash
set -ex

# if PREFIX is not defined, then this was called from an OSX PKG installer
# $2 is the install location, ($HOME by default)
if [ -z "${PREFIX:-}" ]; then
    PREFIX=$(cd "$2/__NAME_LOWER__"; pwd)
fi

# tests
# base environment uses python 3.9
test -f "$PREFIX/conda-meta/history"
"$PREFIX/bin/python" -c "from sys import version_info; assert version_info[:2] == (3, 9)"
"$PREFIX/bin/python" -m pip -V

# extra env named 'py310' uses python 3.10
test -f "$PREFIX/envs/py310/conda-meta/history"
"$PREFIX/envs/py310/bin/python" -c "from sys import version_info; assert version_info[:2] == (3, 10)"
"$PREFIX/envs/py310/bin/python" -m pip -V

# this env only contains dav1d, no python; it should have been created with no errors,
# even if we had excluded tk from the package list
test -f "$PREFIX/envs/dav1d/conda-meta/history"
test ! -f "$PREFIX/envs/dav1d/bin/python"
"$PREFIX/envs/dav1d/bin/dav1d" --version
