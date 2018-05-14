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

if [ -f "$PREFIX/pkgs/__PYTHON_DIST__/bin/python" ]; then
    # Using hardlinks.
    PYTHON="$PREFIX/pkgs/__PYTHON_DIST__/bin/python"
    INSTARG=""
else
    # Not using hardlinks.
    PYTHON="$PREFIX/bin/python"
    INSTARG="--multi"
fi

"$PYTHON" -E -V
if (( $? )); then
    echo "ERROR running Python"
    exit 1
fi

# run post-link, and create the conda metadata
unset FORCE
"$PYTHON" -E -s "$PREFIX/pkgs/.install.py" $INSTARG || exit 1
if [ ! -f "$PREFIX/pkgs/__PYTHON_DIST__/bin/python" ]; then
    rm -rf "$PREFIX/info" || true
fi

__WRITE_CONDARC__

# This is unneeded for the default install to ~, but if the user changes the
# install location, the permissions will default to root unless this is done.
chown -R $USER "$PREFIX"

echo "installation finished."

exit 0
