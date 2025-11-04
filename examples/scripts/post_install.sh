#!/bin/bash

set -euxo pipefail
# the ^u here will cause unbound variables to cause errors
# we use that to test whether these vars are set or not; they should!
echo "Added by post-install script" > "$PREFIX/post_install_sentinel.txt"

echo "INSTALLER_NAME=${INSTALLER_NAME}"
echo "INSTALLER_VER=${INSTALLER_VER}"
echo "INSTALLER_PLAT=${INSTALLER_PLAT}"
echo "INSTALLER_TYPE=${INSTALLER_TYPE}"
echo "INSTALLER_UNATTENDED=${INSTALLER_UNATTENDED}"
echo "CUSTOM_VARIABLE_1=${CUSTOM_VARIABLE_1}"
echo "CUSTOM_VARIABLE_2=${CUSTOM_VARIABLE_2}"
echo "PREFIX=${PREFIX}"

test "${INSTALLER_NAME}" = "Scripts"
test "${INSTALLER_VER}" = "X"
# shellcheck disable=SC2016 # String interpolation disabling is deliberate
test "${CUSTOM_VARIABLE_1}" = 'FIR$T-CUSTOM_'\''STRING'\'' WITH SPACES AND @*! "CHARACTERS"'
# shellcheck disable=SC2016 # String interpolation disabling is deliberate
test "${CUSTOM_VARIABLE_2}" = '$ECOND-CUSTOM_'\''STRING'\'' WITH SPACES AND @*! "CHARACTERS"'

test "${INSTALLER_UNATTENDED}" = "1"

# Print to stderr if any of the input variables are set, and returns 1 - otherwise 0.
# Note that variables that are set but are empty strings will also trigger an error.
# All input variables are checked before exit.
verify_var_is_unset() {
    local failed=0
    for var in "$@"; do
        if [[ -n "${!var+x}" ]]; then
            echo "Error: environment variable $var must be unset." >&2
            failed=1
        fi
    done
    return $failed
}

if [[ $(uname -s) == "Linux" ]]; then
    if [[ ${INSTALLER_PLAT} != linux-* ]]; then
        echo "Error: INSTALLER_PLAT must match 'linux-*' on Linux systems."
        exit 1
    fi

    if ! verify_var_is_unset LD_LIBRARY_PATH LD_PRELOAD LD_AUDIT; then
        echo "Error: One or more of LD_LIBRARY_PATH, LD_PRELOAD, or LD_AUDIT are set."
        exit 1
    fi

else  # macOS
    if [[ ${INSTALLER_PLAT} != osx-* ]]; then
        echo "Error: INSTALLER_PLAT must match 'osx-*' on macOS systems."
        exit 1
    fi

    if ! verify_var_is_unset \
        DYLD_LIBRARY_PATH \
        DYLD_FALLBACK_LIBRARY_PATH \
        DYLD_INSERT_LIBRARIES \
        DYLD_FRAMEWORK_PATH; then
        echo "Error: One or more DYLD_* environment variables are set."
        exit 1
    fi
fi
test -f "${PREFIX}/pre_install_sentinel.txt"
