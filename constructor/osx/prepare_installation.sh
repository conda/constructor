#!/bin/bash
# Copyright (c) 2017 Anaconda, Inc.
# All rights reserved.

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
CONDA_EXEC="$PREFIX/{{ conda_exe_name }}"
# Installers should ignore pre-existing configuration files.
unset CONDARC
unset MAMBARC
# /COMMON UTILS

chmod +x "$CONDA_EXEC"

{%- if conda_exe_name != "_conda" or conda_exe_name != conda.exe %}
# In case there are packages that depend on _conda
ln -s "$CONDA_EXEC" "$PREFIX"/_conda
{%- endif %}

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
{%- if virtual_specs %}
notify "Checking virtual specs compatibility: {{ virtual_specs }}"
CONDA_SOLVER="classic" \
CONDA_PKGS_DIRS="$(mktemp -d)" \
SYSTEM_VERSION_COMPAT=0 \
"$CONDA_EXEC" create --dry-run --prefix "$PREFIX/envs/_virtual_specs_checks" --offline {{ virtual_specs }} {{ no_rcs_arg }}
{%- endif %}

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
