#!/bin/bash
# Copyright (c) 2017 Anaconda, Inc.
# All rights reserved.

# Created by constructor {{ constructor_version }}

# COMMON UTILS
# If you update this block, please propagate changes to the other scripts using it
set -euo pipefail

notify() {
# shellcheck disable=SC2050
{%- if progress_notifications %}
osascript <<EOF
display notification "$1" with title "📦 Install {{ installer_name }} {{ installer_version }}"
EOF
{%- endif %}
logger -p "install.info" "$1" || echo "$1"
}

unset DYLD_LIBRARY_PATH

PREFIX="$2/{{ pkg_name_lower }}"
PREFIX=$(cd "$PREFIX"; pwd)
export PREFIX
echo "PREFIX=$PREFIX"
CONDA_EXEC="$PREFIX/_conda"
# /COMMON UTILS

# Check whether the user wants shortcuts or not
# See check_shortcuts.sh script for details
ENABLE_SHORTCUTS="{{ enable_shortcuts }}"
if [[ -f "$PREFIX/pkgs/user_wants_shortcuts" ]]; then  # this implies ENABLE_SHORTCUTS==true
    shortcuts="{{ shortcuts }}"
elif [[ "$ENABLE_SHORTCUTS" == "incompatible" ]]; then
    shortcuts=""
else
    shortcuts="--no-shortcuts"
fi

# Perform the conda install
notify "Installing packages. This might take a few minutes."
# shellcheck disable=SC2086
if ! \
CONDA_REGISTER_ENVS="{{ register_envs }}" \
CONDA_ROOT_PREFIX="$PREFIX" \
CONDA_SAFETY_CHECKS=disabled \
CONDA_EXTRA_SAFETY_CHECKS=no \
CONDA_CHANNELS={{ channels }} \
CONDA_PKGS_DIRS="$PREFIX/pkgs" \
"$CONDA_EXEC" install --offline --file "$PREFIX/pkgs/env.txt" -yp "$PREFIX" $shortcuts {{ no_rcs_arg }}; then
    echo "ERROR: could not complete the conda install"
    exit 1
fi

# Move the prepackaged history file into place
mv "$PREFIX/pkgs/conda-meta/history" "$PREFIX/conda-meta/history"
rm -f "$PREFIX/env.txt"

# Same, but for the extra environments

mkdir -p "$PREFIX/envs"

for env_pkgs in "${PREFIX}"/pkgs/envs/*/; do
    env_name="$(basename "${env_pkgs}")"
    if [[ "${env_name}" == "*" ]]; then
        continue
    fi

    notify "Installing ${env_name} packages..."
    mkdir -p "$PREFIX/envs/$env_name/conda-meta"
    touch "$PREFIX/envs/$env_name/conda-meta/history"

    if [[ -f "${env_pkgs}channels.txt" ]]; then
        env_channels="$(cat "${env_pkgs}channels.txt")"
        rm -f "${env_pkgs}channels.txt"
    else
        env_channels="{{ channels }}"
    fi
    if [[ -f "$PREFIX/pkgs/user_wants_shortcuts" ]]; then  # this implies ENABLE_SHORTCUTS==true
        # This file is guaranteed to exist, even if empty
        env_shortcuts=$(cat "${env_pkgs}shortcuts.txt")
        rm -f "${env_pkgs}shortcuts.txt"
    elif [[ "$ENABLE_SHORTCUTS" == "incompatible" ]]; then
        env_shortcuts=""
    else
        env_shortcuts="--no-shortcuts"
    fi

    # shellcheck disable=SC2086
    CONDA_ROOT_PREFIX="$PREFIX" \
    CONDA_REGISTER_ENVS="{{ register_envs }}" \
    CONDA_SAFETY_CHECKS=disabled \
    CONDA_EXTRA_SAFETY_CHECKS=no \
    CONDA_CHANNELS="$env_channels" \
    CONDA_PKGS_DIRS="$PREFIX/pkgs" \
    "$CONDA_EXEC" install --offline --file "${env_pkgs}env.txt" -yp "$PREFIX/envs/$env_name" $env_shortcuts {{ no_rcs_arg }} || exit 1
    # Move the prepackaged history file into place
    mv "${env_pkgs}/conda-meta/history" "$PREFIX/envs/$env_name/conda-meta/history"
    rm -f "${env_pkgs}env.txt"
done

# Cleanup!
find "$PREFIX/pkgs" -type d -empty -exec rmdir {} \; 2>/dev/null || :

{{ write_condarc }}

if ! "$PREFIX/bin/python" -V; then
    echo "ERROR running Python"
    exit 1
fi

# This is not needed for the default install to ~, but if the user changes the
# install location, the permissions will default to root unless this is done.
chown -R "${USER}" "$PREFIX"
test -d "${HOME}/.conda" && chown -R "${USER}" "${HOME}/.conda"
test -f "${HOME}/.condarc" && chown "${USER}" "${HOME}/.condarc"

notify "Done! Installation is available in $PREFIX."

exit 0
