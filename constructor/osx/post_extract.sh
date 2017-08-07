#!/bin/bash
# Copyright (c) 2017 Continuum Analytics, Inc.
# All rights reserved.

unset DYLD_LIBRARY_PATH

# TODO: We could use syslog instead of echo to log things to the console so
# that they can actually be seen by someone looking for them.

# $2 is the install location, which is ~ by default, but which the user can
# change.
PREFIX="$2/__NAME__"
PREFIX=$(cd "$PREFIX"; pwd)
export PREFIX

echo "PREFIX=$PREFIX"

mkdir "$PREFIX/envs"

PYTHON="$PREFIX/bin/python"
"$PYTHON" -E -V
if (( $? )); then
    echo "ERROR running Python"
    exit 1
fi

echo "creating default environment..."
# Since the package installer cannot install into an existing location, it
# is best to unset FORCE completely.  The link process would fail if existing
# link targets exist, but we always ensure that we have non-overlapping
# conda packages in the installer.
unset FORCE
"$PYTHON" -E -s "$PREFIX/pkgs/.install.py" --root-prefix="$PREFIX" || exit 1

# This is unneeded for the default install to ~, but if the user changes the
# install location, the permissions will default to root unless this is done.
chown -R $USER "$PREFIX"

echo "installation finished."

exit 0
