#!/bin/bash
# Copyright (c) 2012-2017 Anaconda, Inc.
# All rights reserved.

# $2 is the install location, which is ~ by default, but which the user can
# change.
set -eux

PREFIX="$2/{{ pkg_name_lower }}"
PREFIX=$(cd "$PREFIX"; pwd)
INIT_FILES=$("$PREFIX/bin/python" -m conda init --all | tee)

# Just like in run_install.sh, the files generated by the installer
# are owned by root when installed outside of $HOME. So, ownership of
# files modified by conda init must be changed to belong to $USER.
# For shells like fish or powershell, conda init creates subdirectories
# inside $HOME and/or $PREFIX, so ensure that parent directories also
# have the correct owner.
if [[ "${USER}" != "root" ]]; then
    echo "Fixing permissions..."
    MODIFIED_FILES=()
    while read -r line; do
        MODIFIED_FILES+=("$line")
    done <<< "$(\
      echo "${INIT_FILES}" |\
      grep -E "^modified" |\
      sed -e 's/^modified */' |\
      # Only grab files inside $HOME or $PREFIX.
      # All init files should be there, but that may change, and it
      # is better to miss files than to have an infinite loop below.
      grep -E "^(${HOME}|${PREFIX})"\
    )"
    for file in "${MODIFIED_FILES[@]}"; do
        # Defend against potential empty lines
        if [[ "${file}" == "" ]]; then
            continue
        fi
        while [[ "${file}" != "${HOME}" ]] && [[ "${file}" != "${PREFIX}" ]]; do
            # Check just in case the file wasn't created due to flaky conda init
            if [[ -f "${file}" ]] || [[ -d "${file}" ]]; then
                OWNER=$(stat -f "%u" "${file}" | id -un)
                if [[ "${OWNER}" == "root" ]]; then
                    chown "${USER}" "${file}"
                fi
            fi
            file="${file%/*}"
        done
    done
fi
