#!/bin/bash
# Copyright (c) 2017 Anaconda, Inc.
# All rights reserved.

unset DYLD_LIBRARY_PATH

# TODO: We could use syslog instead of echo to log things to the console so
# that they can actually be seen by someone looking for them.

# $2 is the install location, which is ~ by default, but which the user can
# change.
PREFIX="$2/__NAME_LOWER__"
PREFIX=$(cd "$PREFIX"; pwd)
export PREFIX

echo "PREFIX=$PREFIX"

CONDA_EXEC="$PREFIX/conda.exe"
chmod +x "$CONDA_EXEC"

cp "$PREFIX/conda-meta/history" "$PREFIX/conda-meta/history.bak"
CONDA_SAFETY_CHECKS=disabled \
CONDA_EXTRA_SAFETY_CHECKS=no \
CONDA_CHANNELS=__CHANNELS__ \
CONDA_PKGS_DIRS="$PREFIX/pkgs" \
"$CONDA_EXEC" install --offline --file "$PREFIX/pkgs/env.txt" -yp "$PREFIX" || exit 1
cp "$PREFIX/conda-meta/history.bak" "$PREFIX/conda-meta/history"

# Cleanup!
rm -f "$CONDA_EXEC"
rm -f "$PREFIX/pkgs/env.txt"

__WRITE_CONDARC__

"$PREFIX/bin/python" -V
if (( $? )); then
    echo "ERROR running Python"
    exit 1
fi

# This is unneeded for the default install to ~, but if the user changes the
# install location, the permissions will default to root unless this is done.
chown -R $USER "$PREFIX"

echo "installation finished."

exit 0
