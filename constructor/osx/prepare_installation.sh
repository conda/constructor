#!/bin/bash
# Copyright (c) 2017 Anaconda, Inc.
# All rights reserved.

# COMMON UTILS
# If you update this block, please propagate changes to the other scripts using it
set -euo pipefail

notify() {
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
CONDA_EXEC="$PREFIX/conda.exe"
# /COMMON UTILS

chmod +x "$CONDA_EXEC"

# Create a blank history file so conda thinks this is an existing env
mkdir -p "$PREFIX/conda-meta"
touch "$PREFIX/conda-meta/history"

# Extract the conda packages but avoiding the overwriting of the
# custom metadata we have already put in place
notify "Preparing packages..."
"$CONDA_EXEC" constructor --prefix "$PREFIX" --extract-conda-pkgs
if (( $? )); then
    echo "ERROR: could not extract the conda packages"
    exit 1
fi

exit 0
