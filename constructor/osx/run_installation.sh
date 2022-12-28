#!/bin/bash
# Copyright (c) 2017 Anaconda, Inc.
# All rights reserved.

# COMMON UTILS
# If you update this block, please propagate changes to the other scripts using it
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

# Perform the conda install
notify "Installing packages. This might take a few minutes."
CONDA_SAFETY_CHECKS=disabled \
CONDA_EXTRA_SAFETY_CHECKS=no \
CONDA_CHANNELS=__CHANNELS__ \
CONDA_PKGS_DIRS="$PREFIX/pkgs" \
"$CONDA_EXEC" install --offline --file "$PREFIX/pkgs/env.txt" -yp "$PREFIX" || exit 1
if (( $? )); then
    echo "ERROR: could not complete the conda install"
    exit 1
fi

# Move the prepackaged history file into place
mv "$PREFIX/pkgs/conda-meta/history" "$PREFIX/conda-meta/history"
rm -f "$PREFIX/env.txt"

# Same, but for the extra environments

mkdir -p $PREFIX/envs

for env_pkgs in ${PREFIX}/pkgs/envs/*/; do
    env_name=$(basename ${env_pkgs})
    if [[ "${env_name}" == "*" ]]; then
        continue
    fi

    notify "Installing ${env_name} packages..."
    mkdir -p "$PREFIX/envs/$env_name/conda-meta"
    touch "$PREFIX/envs/$env_name/conda-meta/history"

    if [[ -f "${env_pkgs}channels.txt" ]]; then
        env_channels=$(cat "${env_pkgs}channels.txt")
        rm -f "${env_pkgs}channels.txt"
    else
        env_channels=__CHANNELS__
    fi
    # TODO: custom channels per env?
    # TODO: custom shortcuts per env?
    CONDA_SAFETY_CHECKS=disabled \
    CONDA_EXTRA_SAFETY_CHECKS=no \
    CONDA_CHANNELS="$env_channels" \
    CONDA_PKGS_DIRS="$PREFIX/pkgs" \
    "$CONDA_EXEC" install --offline --file "${env_pkgs}env.txt" -yp "$PREFIX/envs/$env_name" || exit 1
    # Move the prepackaged history file into place
    mv "${env_pkgs}/conda-meta/history" "$PREFIX/envs/$env_name/conda-meta/history"
    rm -f "${env_pkgs}env.txt"
done

# Cleanup!
rm -f "$CONDA_EXEC"
find "$PREFIX/pkgs" -type d -empty -exec rmdir {} \; 2>/dev/null || :

__WRITE_CONDARC__

"$PREFIX/bin/python" -V
if (( $? )); then
    echo "ERROR running Python"
    exit 1
fi

# This is unneeded for the default install to ~, but if the user changes the
# install location, the permissions will default to root unless this is done.
chown -R $USER "$PREFIX"

notify "Done! Installation is available in $PREFIX."

exit 0
