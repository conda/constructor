#!/bin/bash
set -euxo pipefail
# the ^u here will cause unbound variables to cause errors
# we use that to test whether these vars are set or not; they should!
echo "INSTALLER_NAME=${INSTALLER_NAME}"
echo "INSTALLER_VER=${INSTALLER_VER}"
echo "INSTALLER_PLAT=${INSTALLER_PLAT}"
echo "INSTALLER_TYPE=${INSTALLER_TYPE}"
echo "CUSTOM_VARIABLE_1=${CUSTOM_VARIABLE_1}"
echo "CUSTOM_VARIABLE_2=${CUSTOM_VARIABLE_2}"
echo "PREFIX=${PREFIX}"

test "${INSTALLER_NAME}" = "Scripts"
test "${INSTALLER_VER}" = "X"
test "${CUSTOM_VARIABLE_1}" = 'FIR$T CUSTOM '\''STRING'\'' WITH SPACES AND @*#! "CHARACTERS"'
test "${CUSTOM_VARIABLE_2}" = '$ECOND CUSTOM '\''STRING'\'' WITH SPACES AND @*#! "CHARACTERS"'

if [[ $(uname -s) == Linux ]]; then
    if [[ ${INSTALLER_PLAT} != linux-* ]]; then
        exit 1
    fi
else  # macOS
    if [[ ${INSTALLER_PLAT} != osx-* ]]; then
        exit 1
    fi
fi
echo "Added by pre-install script" > "$PREFIX/pre_install_sentinel.txt"
