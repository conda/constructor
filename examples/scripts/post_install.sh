#!/bin/bash

set -euxo pipefail
# the ^u here will cause unbound variables to cause errors
# we use that to test whether these vars are set or not; they should!
echo "INSTALLER_NAME=${INSTALLER_NAME}"
echo "INSTALLER_VER=${INSTALLER_VER}"
echo "INSTALLER_PLAT=${INSTALLER_PLAT}"
echo "INSTALLER_TYPE=${INSTALLER_TYPE}"

test "${INSTALLER_NAME}" = "Scripts"
test "${INSTALLER_VER}" = "X"
if [[ $(uname -s) == Linux ]]; then
    if [[ ${INSTALLER_PLAT} != linux-* ]]; then
        exit 1
    fi
else  # macOS
    if [[ ${INSTALLER_PLAT} != osx-* ]]; then
        exit 1
    fi
fi
test -f "${PREFIX}/pre_install_sentinel.txt"
