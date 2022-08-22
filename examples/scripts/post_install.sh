#!/bin/bash

set -euxo pipefail

if [[ ${INSTALLER_TYPE:-} == "SH" ]]; then
    # pre_install not available on osx pkg yet
    test -f "${PREFIX}/pre_install_sentinel.txt"
fi
