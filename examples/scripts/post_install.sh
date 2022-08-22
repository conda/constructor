#!/bin/bash

set -euxo pipefail
# the ^u here will cause unbound variables to cause errors
# we use that to test whether these vars are set or not; they should!
echo "INSTALLER_NAME=${INSTALLER_NAME}"
echo "INSTALLER_VER=${INSTALLER_VER}"
echo "INSTALLER_PLAT=${INSTALLER_PLAT}"
# TODO: PKG pending
# echo "INSTALLER_TYPE=${INSTALLER_TYPE}"
if [[ ${INSTALLER_TYPE:-} == "SH" ]]; then
    # pre_install not available on osx pkg yet
    test -f "${PREFIX}/pre_install_sentinel.txt"
fi
