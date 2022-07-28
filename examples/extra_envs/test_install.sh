#!/bin/bash
set -ex

# if PREFIX is not defined, then this was called from an OSX PKG installer
# $2 is the install location, ($HOME by default)
if [ xxx$PREFIX = 'xxx' ]; then
    PREFIX=$(cd "$2/__NAME_LOWER__"; pwd)
fi

# tests
# base environment uses python 3.7
test -f "$PREFIX/conda-meta/history"
"$PREFIX/bin/python" -c "from sys import version_info; assert version_info[:2] == (3, 7)"
"$PREFIX/envs/py38/bin/python" -c "import tkinter"

# extra env named 'py38' uses python 3.8
test -f "$PREFIX/envs/py38/conda-meta/history"
"$PREFIX/envs/py38/bin/python" -c "from sys import version_info; assert version_info[:2] == (3, 8)"
# this env shouldn't have tkinter
"$PREFIX/envs/py38/bin/python" -c "import tkinter" && exit 1

# extra env named 'py39' uses python 3.9
test -f "$PREFIX/envs/py39/conda-meta/history"
"$PREFIX/envs/py39/bin/python" -c "from sys import version_info; assert version_info[:2] == (3, 9)"
"$PREFIX/envs/py38/bin/python" -c "import tkinter"
