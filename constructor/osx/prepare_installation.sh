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

chmod +x "$CONDA_EXEC"

# Create a blank history file so conda thinks this is an existing env
mkdir -p "$PREFIX/conda-meta"
touch "$PREFIX/conda-meta/history"

# Check whether the virtual specs can be satisfied
# We need to specify CONDA_SOLVER=classic for conda-standalone
# to work around this bug in conda-libmamba-solver:
# https://github.com/conda/conda-libmamba-solver/issues/480
# micromamba needs an existing pkgs_dir to operate even offline,
# but we haven't created $PREFIX/pkgs yet... do it in a temporary location
# shellcheck disable=SC2050
if [ "__VIRTUAL_SPECS__" != "" ]; then
    notify 'Checking virtual specs compatibility: __VIRTUAL_SPECS__'
    CONDA_SOLVER="classic" \
    CONDA_PKGS_DIRS="$(mktemp -d)" \
    "$CONDA_EXEC" create --dry-run --prefix "$PREFIX" --offline __VIRTUAL_SPECS__
fi

# Create $PREFIX/.nonadmin if the installation didn't require superuser permissions
if [ "$(id -u)" -ne 0 ]; then
    touch "$PREFIX/.nonadmin"
fi

# Extract the conda packages but avoiding the overwriting of the
# custom metadata we have already put in place
notify "Preparing packages..."
if ! "$CONDA_EXEC" constructor --prefix "$PREFIX" --extract-conda-pkgs; then
    echo "ERROR: could not extract the conda packages"
    exit 1
fi

exit 0
