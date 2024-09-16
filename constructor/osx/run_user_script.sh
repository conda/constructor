#!/bin/bash
# Copyright (c) 2017 Anaconda, Inc.
# All rights reserved.

# COMMON UTILS
# If you update this block, please propagate changes to the other scripts using it
set -euo pipefail

notify() {
# shellcheck disable=SC2050
if [ "__PROGRESS_NOTIFICATIONS__" = "True" ]; then
osascript <<EOF
display notification "$1" with title "📦 Install __NAME__ __VERSION__"
EOF
fi
logger -p "install.info" "$1" || echo "$1"
}

unset DYLD_LIBRARY_PATH

PREFIX="$2/__NAME_LOWER__"
PREFIX=$(cd "$PREFIX"; pwd)
export PREFIX
echo "PREFIX=$PREFIX"
CONDA_EXEC="$PREFIX/_conda"
# /COMMON UTILS
# Set this variable to prevent existing .condarc file from interfering with the installation
# Requires conda-standalone 24.9.0 or newer
export CONDA_RESTRICT_RC_SEARCH_PATH=1

# Expose these to user scripts as well
export INSTALLER_NAME="__NAME__"
export INSTALLER_VER="__VERSION__"
export INSTALLER_PLAT="__PLAT__"
export INSTALLER_TYPE="PKG"
export PRE_OR_POST="__PRE_OR_POST__"
_SCRIPT_ENV_VARIABLES_=''  # Templated extra environment variable(s)

# Run user-provided script
if [ -f "$PREFIX/pkgs/user_${PRE_OR_POST}" ]; then
    notify "Running ${PRE_OR_POST} scripts..."
    chmod +x "$PREFIX/pkgs/user_${PRE_OR_POST}"
    if ! "$PREFIX/pkgs/user_${PRE_OR_POST}"; then
        echo "ERROR: could not run user-provided ${PRE_OR_POST} script!"
        exit 1
    fi
else
    echo "ERROR: SHOULD HAVE RUN!"
    exit 1
fi

exit 0
