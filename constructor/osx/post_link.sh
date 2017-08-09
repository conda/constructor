#!/bin/bash
# Copyright (c) 2017 Continuum Analytics, Inc.
# All rights reserved.

unset DYLD_LIBRARY_PATH

# $2 is the install location, which is ~ by default, but which the user can
# change.
PREFIX="$2/__NAME__"
PREFIX=$(cd "$PREFIX"; pwd)
export PREFIX

PYTHON="$PREFIX/bin/python"

unset FORCE
# run 'post-link', and create the conda metadata
"$PYTHON" -E -s "$PREFIX/pkgs/.install.py" || exit 1

exit 0
