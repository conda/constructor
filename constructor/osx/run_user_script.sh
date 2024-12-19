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
display notification "$1" with title "📦 Install __NAME__ __VERSION__"
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

# Expose these to user scripts as well
export INSTALLER_NAME="{{ installer_name }}"
export INSTALLER_VER="{{ installer_version }}"
export INSTALLER_PLAT="{{ installer_platform }}"
export INSTALLER_TYPE="PKG"
# The value for COMMAND_LINE_INSTALL is not documented,
# but it is unset for interactive installations. To be
# safe, set the variable for non-interactive installation
# in a roundabout way.
export INSTALLER_UNATTENDED="${COMMAND_LINE_INSTALL:-0}"
if [[ "${INSTALLER_UNATTENDED}" != "0" ]]; then
    INSTALLER_UNATTENDED="1"
fi
export PRE_OR_POST="{{ pre_or_post }}"
{{ script_env_variables }}

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
